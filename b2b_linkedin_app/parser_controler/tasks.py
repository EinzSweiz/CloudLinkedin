# IMPROVED tasks.py - Fixed Google Sheets integration

import random
import logging
import time

from django.core.cache import cache
from django_redis import get_redis_connection
from django.utils import timezone

from celery import shared_task
from redis.lock import Lock
from redis.client import Redis
import redis

from authorization.models import User
from mailer.models import MessagesBlueprintText
from mailer.tasks import smtp_send_mail

from parser_controler.utils import save_parsing_info, WebSocketBroadcaster
from parser.engine.linkedin.search_profiles import search_linkedin_profiles
from parser_controler.models import ParserRequest, ParsingInfo
from exporter.google_sheets_exporter import GoogleSheetsExporter

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="export_to_google_sheets", max_retries=3)
def export_to_google_sheets(self, profile_data, parser_request_id=None):
    """
    Export a single profile to Google Sheets
    
    Args:
        profile_data: Dict with profile information
        parser_request_id: Optional request ID for tracking
    """
    try:
        logger.info(f"📊 Exporting to Google Sheets: {profile_data.get('full_name', 'Unknown')}")
        
        # Initialize the exporter
        exporter = GoogleSheetsExporter()
        
        # Write the profile to Google Sheets
        exporter.write_profile(profile_data)
        
        logger.info(f"✅ Successfully exported to Google Sheets: {profile_data.get('full_name', 'Unknown')}")
        
        return {
            "success": True,
            "profile_name": profile_data.get('full_name', 'Unknown'),
            "exported_at": timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to export to Google Sheets: {e}")
        
        # Retry the task with exponential backoff
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying Google Sheets export (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
        else:
            logger.error(f"💥 Max retries exceeded for Google Sheets export: {profile_data.get('full_name', 'Unknown')}")
            return {
                "success": False,
                "error": str(e),
                "profile_name": profile_data.get('full_name', 'Unknown')
            }

@shared_task(bind=True, name="batch_export_to_google_sheets")
def batch_export_to_google_sheets(self, profiles_data, parser_request_id=None):
    """
    Export multiple profiles to Google Sheets in a batch
    
    Args:
        profiles_data: List of profile dictionaries
        parser_request_id: Optional request ID for tracking
    """
    try:
        logger.info(f"📊 Batch exporting {len(profiles_data)} profiles to Google Sheets")
        
        exporter = GoogleSheetsExporter()
        
        successful_exports = 0
        failed_exports = 0
        
        for i, profile_data in enumerate(profiles_data):
            try:
                exporter.write_profile(profile_data)
                successful_exports += 1
                logger.info(f"✅ Exported {i+1}/{len(profiles_data)}: {profile_data.get('full_name', 'Unknown')}")
                
                # Small delay to avoid hitting Google API rate limits
                if i > 0 and i % 10 == 0:  # Every 10 profiles
                    time.sleep(1)
                    
            except Exception as profile_error:
                failed_exports += 1
                logger.error(f"❌ Failed to export profile {i+1}: {profile_error}")
                continue
        
        logger.info(f"📊 Batch export completed: {successful_exports} successful, {failed_exports} failed")
        
        return {
            "success": True,
            "total_profiles": len(profiles_data),
            "successful_exports": successful_exports,
            "failed_exports": failed_exports
        }
        
    except Exception as e:
        logger.error(f"❌ Batch export to Google Sheets failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "total_profiles": len(profiles_data)
        }

LOCK_EXPIRE = 60 * 60  # 1 hour

@shared_task(bind=True, name="start_parsing")
def start_parsing(self, keywords, location, limit, start_page, end_page, parser_request_id=None, user_email=None, creator_email=None, creator_id=None):
    redis_conn = redis.StrictRedis(host="redis", port=6379, db=0)
    lock = redis_conn.lock(f"start_parsing_lock_{parser_request_id}", timeout=LOCK_EXPIRE)

    logger.info(f"Starting parsing task for request ID: {parser_request_id}")
    
    # Initialize WebSocket broadcaster
    broadcaster = WebSocketBroadcaster(parser_request_id) if parser_request_id else None

    try:
        with lock:
            logger.info("Lock acquired — starting parsing task.")
            
            # Send initial WebSocket update
            if broadcaster:
                broadcaster.send_update(
                    action='parsing_started',
                    message=f'🚀 Starting LinkedIn search for {keywords} in {location}',
                    data={'keywords': keywords, 'location': location, 'limit': limit}
                )

            # Get the parser request object for updates
            parser_request = None
            if parser_request_id:
                try:
                    parser_request = ParserRequest.objects.get(id=parser_request_id)
                    parser_request.status = 'running'
                    parser_request.current_page = start_page
                    parser_request.started_at = timezone.now()
                    parser_request.save(update_fields=['status', 'current_page', 'started_at'])
                    logger.info(f"Parser request {parser_request_id} status set to 'running'")
                    
                    if broadcaster:
                        broadcaster.send_update(
                            action='status_changed',
                            message='Status updated to running',
                            data={'status': 'running', 'current_page': start_page}
                        )
                        
                except ParserRequest.DoesNotExist:
                    logger.error(f"Parser request {parser_request_id} not found")
                    return

            # Parse keywords properly
            try:
                if isinstance(keywords, str):
                    try:
                        import json
                        parsed_keywords = json.loads(keywords)
                        if isinstance(parsed_keywords, list):
                            keywords = parsed_keywords
                        else:
                            keywords = [str(keywords)]
                    except json.JSONDecodeError:
                        # Handle comma-separated or space-separated
                        if ',' in keywords:
                            keywords = [k.strip() for k in keywords.split(',')]
                        elif ' ' in keywords and not keywords.startswith('['):
                            keywords = [k.strip() for k in keywords.split()]
                        else:
                            keywords = [keywords]
                elif not isinstance(keywords, list):
                    keywords = [str(keywords)]

                logger.info(f"🔍 Parsed keywords: {keywords}")
                
                if broadcaster:
                    broadcaster.send_log('INFO', 'SEARCH', f'Parsed keywords: {keywords}')

                logger.info(f"🚀 Starting LinkedIn search with WebSocket support")
                
                if broadcaster:
                    broadcaster.send_update(
                        action='search_starting',
                        message=f'Initializing LinkedIn search engine...',
                        data={'phase': 'initialization'}
                    )
                
                # Call search function with WebSocket support
                profiles = search_linkedin_profiles(
                    keywords=keywords,
                    location=location,
                    limit=limit,
                    start_page=start_page,
                    end_page=end_page,
                    parser_request_id=parser_request_id  # ✅ This enables WebSocket!
                )
                
                logger.info(f"✅ Search completed with {len(profiles)} profiles")
                
                if broadcaster:
                    broadcaster.send_update(
                        action='search_completed',
                        message=f'Search completed! Found {len(profiles)} profiles',
                        data={'total_profiles': len(profiles), 'phase': 'saving'}
                    )

                # REAL-TIME PROCESSING: Save profiles one by one with progress updates
                saved_count = 0
                emails_count = 0
                sheets_exported_count = 0  # 🔥 FIX: Initialize this variable
                
                if broadcaster:
                    broadcaster.send_update(
                        action='saving_started',
                        message='Starting to save profiles to database and Google Sheets...',
                        data={'total_to_save': len(profiles)}
                    )
                
                for i, profile in enumerate(profiles):
                    try:
                        # Send progress update before saving
                        if broadcaster:
                            broadcaster.send_update(
                                action='saving_profile',
                                message=f'Saving profile {i+1}/{len(profiles)}: {profile.get("name", "Unknown")}',
                                data={
                                    'current_index': i+1,
                                    'total': len(profiles),
                                    'profile_name': profile.get("name", "Unknown"),
                                    'company': profile.get("company", "Unknown")
                                }
                            )
                        
                        # Save to DATABASE first
                        result = save_parsing_info(
                            full_name=profile.get("name", ""),
                            position=profile.get("position", ""),
                            company_name=profile.get("company", ""),
                            email=profile.get("email", None),
                            profile_url=profile.get("profile_url", None),
                            parser_request_id=parser_request_id,
                            creator_email=creator_email,
                            creator_id=creator_id,
                        )
                        
                        if result:
                            saved_count += 1
                            if profile.get("email"):
                                emails_count += 1
                                
                                # Send email if configured
                                user = User.objects.filter(email=user_email).first()
                                message_blueprint_obj = MessagesBlueprintText.objects.filter(
                                    creator=user
                                ).order_by("?").first() if user else None

                                if message_blueprint_obj:
                                    smtp_send_mail.delay(message_blueprint_obj.id, result.id)
                            
                            # 🔥 GOOGLE SHEETS EXPORT
                            try:
                                # Prepare data for Google Sheets (matching your exporter format)
                                sheets_data = {
                                    "full_name": profile.get("name", ""),
                                    "position": profile.get("position", ""),
                                    "company_name": profile.get("company", ""),
                                    "email": profile.get("email", ""),
                                    "profile_url": profile.get("profile_url", ""),
                                }
                                
                                # Call the Google Sheets export task asynchronously
                                export_result = export_to_google_sheets.delay(
                                    profile_data=sheets_data,
                                    parser_request_id=parser_request_id
                                )
                                
                                # Optional: Wait for the result if you want immediate feedback
                                try:
                                    sheets_result = export_result.get(timeout=10)  # 10 second timeout
                                    if sheets_result.get('success'):
                                        sheets_exported_count += 1
                                        logger.info(f"📊 Google Sheets export success: {profile.get('name', 'Unknown')}")
                                        
                                        if broadcaster:
                                            broadcaster.send_log('INFO', 'SHEETS', f'✅ Exported to Google Sheets: {profile.get("name", "Unknown")}')
                                    else:
                                        logger.warning(f"📊 Google Sheets export failed: {sheets_result.get('error')}")
                                        if broadcaster:
                                            broadcaster.send_log('WARNING', 'SHEETS', f'❌ Failed to export: {profile.get("name", "Unknown")}')
                                except Exception as timeout_error:
                                    # If timeout, the task is still running in background
                                    logger.info(f"📊 Google Sheets export queued (background): {profile.get('name', 'Unknown')}")
                                    if broadcaster:
                                        broadcaster.send_log('INFO', 'SHEETS', f'📋 Queued for export: {profile.get("name", "Unknown")}')
                                
                            except Exception as sheets_error:
                                logger.error(f"📊 Error initiating Google Sheets export: {sheets_error}")
                                if broadcaster:
                                    broadcaster.send_log('ERROR', 'SHEETS', f'Export error: {str(sheets_error)}')

                            # Update database immediately for real-time dashboard
                            if parser_request_id:
                                # Calculate current page based on profiles processed
                                estimated_page = start_page + (i // 10)  # Assume ~10 profiles per page
                                current_page = min(estimated_page, end_page)
                                
                                ParserRequest.objects.filter(id=parser_request_id).update(
                                    profiles_found=saved_count,
                                    emails_extracted=emails_count,
                                    current_page=current_page
                                )
                                
                                # Send progress update with Google Sheets info
                                if broadcaster:
                                    broadcaster.send_update(
                                        action='progress_update',
                                        message=f'Progress: {saved_count} profiles saved, {emails_count} with emails, {sheets_exported_count} exported to Sheets',
                                        data={
                                            'saved_count': saved_count,
                                            'emails_count': emails_count,
                                            'sheets_exported_count': sheets_exported_count,
                                            'current_page': current_page,
                                            'progress_percentage': round((i+1) / len(profiles) * 100, 1)
                                        }
                                    )
                                
                            logger.info(f"✅ SAVED profile #{saved_count}: {profile.get('name', 'Unknown')} @ {profile.get('company', 'Unknown')}")
                            
                            # Small delay for real-time dashboard effect
                            time.sleep(0.5)  # Increased slightly for Google Sheets processing
                            
                    except Exception as save_error:
                        logger.error(f"❌ Error saving profile {i+1}: {save_error}")
                        if broadcaster:
                            broadcaster.send_log('ERROR', 'SAVE', f'Failed to save profile {i+1}: {str(save_error)}')
                        continue

            except Exception as search_error:
                logger.error(f"❌ Search error: {search_error}")
                
                if broadcaster:
                    broadcaster.send_update(
                        action='search_error',
                        message=f'Search failed: {str(search_error)}',
                        data={'error': str(search_error)}
                    )
                
                # Update status to error
                if parser_request_id:
                    ParserRequest.objects.filter(id=parser_request_id).update(
                        status='error',
                        error_message=str(search_error),
                        completed_at=timezone.now()
                    )
                return

            # Final statistics update
            if parser_request_id and parser_request:
                # Get final counts from database
                final_total = ParsingInfo.objects.filter(parser_request=parser_request).count()
                final_emails = ParsingInfo.objects.filter(
                    parser_request=parser_request,
                    email__isnull=False
                ).exclude(email='').count()

                ParserRequest.objects.filter(id=parser_request_id).update(
                    status='completed',
                    completed_at=timezone.now(),
                    profiles_found=final_total,
                    emails_extracted=final_emails,
                    current_page=end_page
                )

                logger.info(f"🎉 Parsing completed successfully. Found {final_total} profiles, {final_emails} with emails, {sheets_exported_count} exported to Google Sheets.")
                
                # Send final completion update
                if broadcaster:
                    broadcaster.send_update(
                        action='parsing_completed',
                        message=f'🎉 Parsing completed! Found {final_total} profiles, {final_emails} with emails, {sheets_exported_count} exported to Sheets',
                        data={
                            'final_total': final_total,
                            'final_emails': final_emails,
                            'sheets_exported': sheets_exported_count,
                            'success_rate': round((final_emails / final_total * 100), 1) if final_total > 0 else 0,
                            'status': 'completed'
                        }
                    )

    except redis.exceptions.LockError:
        logger.warning("⚠️ Lock is already active — skipping this run.")
        if broadcaster:
            broadcaster.send_update(
                action='lock_error',
                message='Another parsing task is already running',
                data={'error': 'lock_conflict'}
            )
        if parser_request_id:
            ParserRequest.objects.filter(id=parser_request_id).update(
                status='error',
                error_message='Another parsing task is already running'
            )
    except Exception as e:
        logger.exception("❌ An error occurred during parsing.")
        if broadcaster:
            broadcaster.send_update(
                action='fatal_error',
                message=f'Fatal error: {str(e)}',
                data={'error': str(e)}
            )
        if parser_request_id:
            ParserRequest.objects.filter(id=parser_request_id).update(
                status='error',
                error_message=str(e),
                completed_at=timezone.now()
            )