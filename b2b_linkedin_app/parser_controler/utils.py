# parser_controler/utils.py - Enhanced for real-time updates
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from .models import ParsingInfo, ParserRequest

logger = logging.getLogger(__name__)
User = get_user_model()


class WebSocketBroadcaster:
    def __init__(self, request_id):
        self.request_id = request_id
        self.channel_layer = None
        self.group_name = f'parsing_{request_id}'

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            self.channel_layer = get_channel_layer()
            self.async_to_sync = async_to_sync
        except ImportError:
            logger.warning("Channels not installed - WebSocket updates disabled")

    def send_update(self, action, message, data=None):
        if self.channel_layer:
            try:
                self.async_to_sync(self.channel_layer.group_send)(
                    self.group_name,
                    {
                        'type': 'parsing_update',
                        'action': action,
                        'message': message,
                        'data': data or {},
                        'timestamp': timezone.now().timestamp()
                    }
                )
                logger.debug(f"📡 WebSocket update sent: {action} - {message}")
            except Exception as e:
                logger.warning(f"Failed to send WebSocket update: {e}")

    def send_log(self, level, logger_name, message):
        if self.channel_layer:
            try:
                self.async_to_sync(self.channel_layer.group_send)(
                    self.group_name,
                    {
                        'type': 'log_message',
                        'level': level,
                        'logger': logger_name,
                        'message': message,
                        'timestamp': timezone.now().timestamp()
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to send WebSocket log: {e}")


def save_parsing_info(full_name, position, company_name, email=None, profile_url=None, parser_request_id=None, creator_email=None, creator_id=None):
    try:
        parser_request = None
        broadcaster = None
        creator = None

        if parser_request_id:
            try:
                parser_request = ParserRequest.objects.get(id=parser_request_id)
                broadcaster = WebSocketBroadcaster(parser_request_id)
            except ParserRequest.DoesNotExist:
                logger.warning(f"Parser request {parser_request_id} not found")

        # FIXED: Try creator_id first, then creator_email
        if creator_id:
            try:
                creator = User.objects.get(id=creator_id)
                logger.info(f"✅ Found creator by ID: {creator.email}")
            except User.DoesNotExist:
                logger.warning(f"User with ID '{creator_id}' not found")
        
        if not creator and creator_email:
            try:
                creator = User.objects.get(email=creator_email)
                logger.info(f"✅ Found creator by email: {creator.email}")
            except User.DoesNotExist:
                logger.warning(f"User with email '{creator_email}' not found")
        
        # CRITICAL: Fallback if no creator found
        if not creator:
            creator = User.objects.filter(is_superuser=True).first()
            if not creator:
                creator = User.objects.first()
                if not creator:
                    logger.error("NO USERS FOUND IN DATABASE!")
                    return None
            logger.warning(f"⚠️ Using fallback creator: {creator.email}")

        full_name = str(full_name).strip() if full_name else ''
        position = str(position).strip() if position else ''
        company_name = str(company_name).strip() if company_name else ''
        email = str(email).strip() if email else None
        profile_url = str(profile_url).strip() if profile_url else None

        if not full_name:
            logger.warning("Skipping profile save: no name provided")
            return None

        if email and (email.lower() in ['none', 'null', '', 'not found', 'n/a'] or '@' not in email):
            email = None

        with transaction.atomic():
            existing_profile = None
            if parser_request:
                existing_profile = ParsingInfo.objects.filter(
                    parser_request=parser_request,
                    full_name__iexact=full_name,
                    company_name__iexact=company_name or ''
                ).first()

            if existing_profile:
                updated = False
                if not existing_profile.email and email:
                    existing_profile.email = email
                    updated = True
                if not existing_profile.position and position:
                    existing_profile.position = position
                    updated = True
                if not existing_profile.profile_url and profile_url:
                    existing_profile.profile_url = profile_url
                    updated = True

                if updated:
                    existing_profile.updated_at = timezone.now()
                    existing_profile.save()
                    logger.info(f"✅ Updated existing profile: {full_name}")

                    if broadcaster:
                        total_count = ParsingInfo.objects.filter(parser_request=parser_request).count()
                        broadcaster.send_update(
                            action='profile_updated',
                            message=f'Updated: {full_name} @ {company_name or "Unknown"}',
                            data={
                                'profile_id': existing_profile.id,
                                'name': full_name,
                                'company': company_name,
                                'email': email,
                                'has_email': bool(email),
                                'total_count': total_count,
                                'is_update': True
                            }
                        )

                    return existing_profile
                else:
                    logger.info(f"ℹ️ Profile already exists: {full_name}")
                    return existing_profile

            profile = ParsingInfo.objects.create(
                parser_request=parser_request,
                creator=creator,
                full_name=full_name,
                position=position or None,
                company_name=company_name or None,
                email=email,
                profile_url=profile_url,
                search_keywords=getattr(parser_request, 'keywords', None) if parser_request else None,
                search_location=getattr(parser_request, 'location', None) if parser_request else None,
                page_found=getattr(parser_request, 'current_page', None) if parser_request else None
            )

            logger.info(f"✅ SAVED: {full_name} @ {company_name or 'Unknown'} ({'with email' if email else 'no email'})")

            if broadcaster:
                total_count = ParsingInfo.objects.filter(parser_request=parser_request).count()
                broadcaster.send_update(
                    action='profile_saved',
                    message=f'Found: {full_name} @ {company_name or "Unknown"}',
                    data={
                        'profile_id': profile.id,
                        'name': full_name,
                        'company': company_name,
                        'email': email,
                        'has_email': bool(email),
                        'total_count': total_count,
                        'is_update': False
                    }
                )

            return profile

    except Exception as e:
        logger.error(f"❌ Error saving profile '{full_name}': {e}")
        return None


def get_parsing_statistics(parser_request_id):
    try:
        parser_request = ParserRequest.objects.get(id=parser_request_id)
        profiles = ParsingInfo.objects.filter(parser_request=parser_request)
        total_profiles = profiles.count()
        profiles_with_email = profiles.exclude(email__isnull=True).exclude(email__exact='').count()

        return {
            'total_profiles': total_profiles,
            'profiles_with_email': profiles_with_email,
            'success_rate': round((profiles_with_email / total_profiles * 100), 1) if total_profiles > 0 else 0,
            'latest_profile': profiles.order_by('-created_at').first(),
            'parser_request': parser_request
        }
    except ParserRequest.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return None


def update_parsing_progress(parser_request_id, current_page=None, profiles_found=None, emails_extracted=None):
    try:
        update_data = {}
        if current_page is not None:
            update_data['current_page'] = current_page
        if profiles_found is not None:
            update_data['profiles_found'] = profiles_found
        if emails_extracted is not None:
            update_data['emails_extracted'] = emails_extracted

        if update_data:
            ParserRequest.objects.filter(id=parser_request_id).update(**update_data)
            logger.debug(f"Updated progress for request {parser_request_id}: {update_data}")

            broadcaster = WebSocketBroadcaster(parser_request_id)
            broadcaster.send_update(
                action='progress_update',
                message=f'Progress: Page {current_page}, {profiles_found} profiles, {emails_extracted} emails',
                data=update_data
            )

    except Exception as e:
        logger.error(f"Error updating progress: {e}")


def cleanup_duplicate_profiles(parser_request_id):
    try:
        profiles = ParsingInfo.objects.filter(parser_request_id=parser_request_id)
        seen = set()
        duplicates = []

        for profile in profiles.order_by('created_at'):
            key = (profile.full_name.lower(), (profile.company_name or '').lower())
            if key in seen:
                duplicates.append(profile.id)
            else:
                seen.add(key)

        if duplicates:
            deleted_count = ParsingInfo.objects.filter(id__in=duplicates).delete()[0]
            logger.info(f"Cleaned up {deleted_count} duplicate profiles")
            return deleted_count

        return 0

    except Exception as e:
        logger.error(f"Error cleaning duplicates: {e}")
        return 0


def validate_email_format(email):
    if not email:
        return False
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return bool(re.match(pattern, email))


def enhance_profile_data(profile_data):
    try:
        if profile_data.get('name'):
            name = ' '.join(profile_data['name'].strip().split())
            profile_data['name'] = name

        if profile_data.get('company'):
            company = profile_data['company'].strip()
            for suffix in ['Inc.', 'LLC', 'Ltd.', 'Corp.', 'Co.']:
                if company.endswith(suffix):
                    company = company[:-len(suffix)].strip()
            profile_data['company'] = company

        if profile_data.get('email'):
            email = profile_data['email'].strip().lower()
            profile_data['email'] = email if validate_email_format(email) else None

        return profile_data

    except Exception as e:
        logger.error(f"Error enhancing profile data: {e}")
        return profile_data
