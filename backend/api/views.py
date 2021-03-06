"""
REST API for GreekGeeks. Refer to the OpenAPI spec for details about request
and response bodies.
"""
from django.db.utils import IntegrityError
from django.core.mail import send_mail
from rest_framework import authentication, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import api.models as models
import api.serializers as serializers
import api.permissions as permissions
from api.tokens import email_verification_token_generator
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
# TODO input validation
# TODO database failure responses (e.g. actually handle instead of 500'ing)
# TODO notifications


class ContactsView(APIView):
    """
    /organizations/{orgId}/contacts/
    """
    permission_classes = [permissions.IsOrganizationMember]
    allowed_methods = ['GET', 'POST']

    def get(self, request, orgId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        # get the contacts and serialize
        contacts = models.Organization.objects.get(uuid=orgId) \
                         .contact_set.all()
        contacts = serializers.ContactSerializer(contacts, many=True)

        return Response(contacts.data, status.HTTP_200_OK)

    def post(self, request, orgId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        data = serializers.ContactAdditionSerializer(data=request.data)
        if data.is_valid():
            org_uuid = data.data['organization_uuid']
            org = models.Organization.objects.get(uuid=org_uuid)

            first_name = data.data['first_name']

            # create contact and update with optional fields
            contact = models.Contact(
                organization=org,
                created_by=request.user,
                first_name=first_name
            )

            if 'last_name' in data.data:
                contact.last_name = data.data['last_name']
            if 'primary_contact_method' in data.data:
                cm = data.data['primary_contact_method']
                cm = models.ContactMethod(
                    contact=contact,
                    medium=cm['medium'],
                    value=cm['value']
                )
                contact.primary_contact_method = cm
            if 'rank_uuid' in data.data:
                rank = models.Organization.objects.get(uuid=org_uuid) \
                    .contactrank_set.get(uuid=data.data['rank_uuid'])

                contact.rank = rank

            contact.save()

            response = {
                'success': True,
                'uuid': contact.uuid
            }
            return Response(response, status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ContactView(APIView):
    """
    /organizations/{orgId}/contacts/{contactId}/
    """
    permission_classes = [permissions.IsOrganizationMember]
    allowed_methods = ['GET', 'POST', 'DELETE']

    def get(self, request, orgId, contactId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        # get the contact and serialize
        contact = models.Organization.objects.get(uuid=orgId) \
                        .contact_set.get(uuid=contactId)
        contact = serializers.ContactSerializer(contact)

        return Response(contact.data, status.HTTP_200_OK)

    def post(self, request, orgId, contactId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        data = serializers.ContactUpdateSerializer(data=request.data)
        if data.is_valid():
            contact = models.Organization.objects.get(uuid=orgId) \
                        .contact_set.get(uuid=contactId)

            # update contact with new fields
            if 'first_name' in data.data:
                contact.first_name = data.data['first_name']
            if 'last_name' in data.data:
                contact.last_name = data.data['last_name']
            if 'primary_contact_method_uuid' in data.data:
                cm_uuid = data.data['primary_contact_method_uuid']
                cm = contact.contactmethod_set.get(uuid=cm_uuid)
                contact.primary_contact_method = cm
            if 'rank_uuid' in data.data:
                rank_uuid = data.data['rank_uuid']
                rank = models.Organization.objects.get(uuid=orgId) \
                             .rank_set.get(uuid=rank_uuid)

            contact.save()

            response = {
                'success': True
            }
            return Response(response, status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, orgId, contactId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        # get contact and delete
        org = models.Organization.objects.get(uuid=orgId)
        contact = org.contact_set.get(uuid=contactId)
        contact.delete()

        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)


class ContactNotesView(APIView):
    """
    /organizations/{orgId}/contacts/{contactId}/notes/
    """
    permission_classes = [permissions.IsOrganizationMember]
    allowed_methods = ['POST']

    def post(self, request, orgId, contactId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        data = serializers.ContactNoteAdditionSerializer(data=request.data)
        if data.is_valid():
            # get contact, and create a note corresponding to it
            contact = models.Organization.get(uuid=orgId) \
                        .contacts_set.get(uuid=contactId)
            body = data.data['body']
            # TODO tag support
            note = models.ContactNote(
                contact=contact,
                created_by=request.user,
                body=body
            )
            note.save()

            response = {
                'success': True
            }
            return Response(response, status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ContactNoteView(APIView):
    """
    /organizations/{orgId}/contacts/{contactId}/notes/{noteId}/
    """
    permission_classes = [permissions.IsOrganizationMember]
    allowed_methods = ['DELETE']

    def delete(self, request, orgId, contactId, noteId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        # get the note, and delete it
        contact = models.Organization.objects.get(uuid=orgId) \
                        .contact_set.get(uuid=contactId)
        note = contact.contactnote_set.get(uuid=noteId)
        note.delete()
        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)


class MembersView(APIView):
    """
    /organizations/{orgId}/members/
    """
    permission_classes = [permissions.IsOrganizationMember]
    allowed_methods = ['GET']

    def get(self, request, orgId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        org = models.Organization.objects.get(uuid=orgId)

        users = org.users.all()

        users = serializers.MemberSerializer(users, many=True)
        return Response(users.data, status.HTTP_200_OK)


class MemberView(APIView):
    """
    /organizations/{orgId}/members/{memberId}/
    """
    permission_classes = [permissions.IsOrganizationAdminOrReadOnly]
    allowed_methods = ['GET', 'DELETE']

    def get(self, request, orgId, memberId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        user = models.Organization.objects.get(uuid=orgId) \
                     .users.get(uuid=memberId)

        user = serializers.MemberSerializer(user)
        return Response(user.data, status=status.HTTP_200_OK)

    def delete(self, request, orgId, memberId):
        obj = {'orgId': orgId}
        self.check_object_permissions(request, obj)

        # only remove the user from the organization, don't delete the user!
        models.Organization.objects.get(uuid=orgId) \
            .users.remove(request.user)

        response = {
            'success': True
        }

        return Response(response, status.HTTP_200_OK)


class RanksView(APIView):
    """
    /organizations/{orgId}/ranks/
    """
    permission_classes = [permissions.IsOrganizationAdminOrReadOnly]
    allowed_methods = ['GET', 'POST']

    def get(self, request, orgId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        ranks = models.Organization.objects.get(uuid=orgId) \
                      .contactrank_set.all()

        ranks = serializers.RankSerializer(data=ranks, many=True)

        return Response(ranks.data, status.HTTP_200_OK)

    def post(self, request, orgId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        data = serializers.RankAdditionSerializer(data=request.data)
        if data.is_valid():
            name = data.data['name']
            description = data.data['description']

            org = models.Organization.objects.get(uuid=orgId)

            rank = models.ContactRank(
                organization=org,
                name=name,
                description=description
            )
            rank.save()

            response = {
                'success': True,
                'uuid': rank.uuid
            }
            return Response(response, status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class RankView(APIView):
    """
    /organizations/{orgId}/ranks/{rankId}/
    """
    permission_classes = [permissions.IsOrganizationAdmin]
    allowed_methods = ['POST']

    def post(self, request, orgId, rankId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        data = serializers.RankUpdateSerializer(data=request.data)
        if data.is_valid():
            description = data.data['description']

            rank = models.Organization.objects.get(uuid=orgId) \
                         .contactrank_set.get(uuid=rankId)
            rank.description = description
            rank.save()

            response = {
                'success': True
            }
            return Response(response, status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class RequestsView(APIView):
    """
    /organizations/{orgId}/requests/
    """
    permission_classes = [permissions.IsOrganizationAdminOrPostOnly]
    allowed_methods = ['GET', 'POST']

    def get(self, request, orgId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        org = models.Organization.objects.get(uuid=orgId)
        reqs = org.membershiprequest_set.all()
        reqs = serializers.MembershipRequestSerializer(reqs, many=True)

        return Response(reqs.data, status.HTTP_200_OK)

    def post(self, request, orgId):
        data = serializers.MembershipRequestAdditionSerializer(
            data=request.data
        )
        if data.is_valid():
            user_uuid = data['user_uuid']
            # we check the object permissions late here because we need
            # the user id from the request object
            obj = {'orgId': orgId, 'userId': user_uuid}
            self.check_object_permissions(request, obj)

            org = models.Organization.objects.get(uuid=orgId)
            user = models.User.objects.get(uuid=user_uuid)

            mr = models.MembershipRequest(
                organization=org,
                user=user
            )
            mr.save()

            response = {
                'success': True,
                'uuid': mr.uuid
            }
            return Response(response, status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class RequestView(APIView):
    """
    /organizations/{orgId}/requests/{requestId}/
    """
    permission_classes = [permissions.IsOrganizationAdminOrDeleteOnly]
    allowed_methods = ['GET', 'POST', 'DELETE']

    def get(self, request, orgId, requestId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        mr = models.Organization.objects.get(uuid=orgId) \
                   .membershiprequest_set.get(uuid=requestId)
        mr = serializers.MembershipRequestSerializer(request)

        return Response(mr.data, status.HTTP_200_OK)

    def post(self, request, orgId, requestId):
        obj = {'orgId': orgId, 'userId': None}
        self.check_object_permissions(request, obj)

        org = models.Organization.objects.get(uuid=orgId)
        mr = org.membershiprequest_set.get(uuid=requestId)

        user = mr.user

        # TODO should probably be executed as transaction or something
        # add user
        org.users.add(user)

        # delete request
        org.membershiprequest_set.remove(mr)

        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)

    def delete(self, request, orgId, requestId):
        org = models.Organizations.objects.get(uuid=orgId)
        mr = org.membershiprequest_set.get(uuid=requestId)

        obj = {'orgId': orgId, 'userId': mr.user.uuid}
        self.check_object_permissions(request, obj)

        # actually delete the object
        mr.delete()

        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)


class UsersView(APIView):
    """
    /users/
    """
    permission_classes = [AllowAny]
    allowed_methods = ['POST']

    def post(self, request, format=None):
        data = serializers.UserAdditionSerializer(data=request.data)
        if data.is_valid():
            email = data.data['email']
            password = data.data['password']
            first_name = data.data['first_name']
            last_name = data.data['last_name']

            try:
                user = models.User.objects.create_user(email,
                                                       password,
                                                       first_name=first_name,
                                                       last_name=last_name)
                user.is_active = False
                user.save()
            except IntegrityError:
                response = {
                    'success': False,
                    'errorMessage': 'Database integrity exception'
                }
                code = status.HTTP_400_BAD_REQUEST
            else:
                response = {
                    'uuid': user.uuid,
                    'success': True
                }
                code = status.HTTP_201_CREATED

            # send email
            token = email_verification_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.uuid))
            url = f'{request.get_host()}/verify?uidb64={uid}&token={token}'
            send_mail(
                'Verify your GreekGeeks Account',
                url,
                'donotreply@greekgeeks.com',
                [email]
            )
            return Response(response, code)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(APIView):
    """
    /users/email/
    """
    permission_classes = [AllowAny]
    allowed_methods = ['POST']

    def post(self, request, format=None):
        data = serializers.EmailVerificationSerializer(data=request.data)
        if data.is_valid():
            uidb64 = data.data['uidb64']
            token = data.data['token']

            try:
                uuid = force_text(urlsafe_base64_decode(uidb64))
                user = models.User.objects.get(uuid=uuid)
            except (TypeError, ValueError, OverflowError,
                    models.User.DoesNotExist):
                user = None

            if user is not None and \
               email_verification_token_generator.check_token(user, token):
                user.is_active = True
                user.save()

                response = {
                    'success': True
                }
                code = status.HTTP_200_OK
            else:
                response = {
                    'success': False
                }
                code = status.HTTP_400_BAD_REQUEST

            return Response(response, code)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class UserView(APIView):
    """
    /users/{userId}/
    """
    permission_classes = [permissions.OwnsAccount]
    allowed_methods = ['GET', 'POST', 'DELETE']

    def get(self, request, userId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        user = models.Users.objects.get(uuid=userId)
        user = serializers.UserSerializer(user)

        return Response(user.data, status.HTTP_200_OK)

    def post(self, request, userId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        user = request.user
        if userId != user.uuid:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = serializers.UserUpdateSerializer(data=request.data)
        if data.is_valid():
            if 'first_name' in data.data:
                user.first_name = data.data['first_name']
            if 'last_name' in data.data:
                user.last_name = data.data['last_name']
            if 'password' in data.data:
                user.set_password(data.data['password'])

            user.save()

            response = {
                'success': True
            }

            return Response(response, status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, userId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        # actually delete the user
        user = models.Users.objects.get(uuid=userId)
        user.delete()

        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)


class NotificationsView(APIView):
    """
    /users/{userId}/notifications/
    """
    permission_classes = [permissions.OwnsAccount]
    allowed_methods = ['GET']

    def get(self, request, userId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        notifications = models.User.objects.get(uuid=userId) \
                              .notification_set.all()

        notifications = serializers.NotificationSerializer(
            notifications.data,
            many=True
        )
        return Response(notifications.data, status.HTTP_200_OK)


class NotificationView(APIView):
    """
    /users/{userId}/notifications/{notificationId}/
    """
    permission_classes = [permissions.OwnsAccount]
    allowed_methods = ['GET', 'DELETE']

    def get(self, request, userId, notificationId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        notification = models.User.objects.get(uuid=userId) \
                             .notification_set.get(uuid=notificationId)

        notification = serializers.NotificationSerializer(notification.data)

        return Response(notification.data, status.HTTP_200_OK)

    def delete(self, request, userId, notificationId):
        obj = {'userId': userId}
        self.check_object_permissions(request, obj)

        notification = models.User.objects.get(uuid=userId) \
                             .notification_set.get(uuid=notificationId)
        notification.delete()

        response = {
            'success': True
        }
        return Response(response, status.HTTP_200_OK)
