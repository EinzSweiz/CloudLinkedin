from django.core.management.base import BaseCommand
from exporter.google_sheets_exporter import GoogleSheetsExporter
import time

class Command(BaseCommand):
    help = 'Test Google Sheets integration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--write-test',
            action='store_true',
            help='Write a test profile to sheets',
        )
        parser.add_argument(
            '--batch-test',
            action='store_true',
            help='Test batch writing (5 test profiles)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing Google Sheets integration...")
        
        try:
            # Initialize exporter
            self.stdout.write("📋 Initializing Google Sheets exporter...")
            exporter = GoogleSheetsExporter()
            
            # Test connection
            self.stdout.write("🔗 Testing connection...")
            if exporter.test_connection():
                self.stdout.write(self.style.SUCCESS("✅ Google Sheets connection successful"))
                
                # Get sheet info
                info = exporter.get_sheet_info()
                if info and "error" not in info:
                    self.stdout.write(f"📊 Spreadsheet: {info['title']}")
                    self.stdout.write(f"🔗 URL: {info['url']}")
                    self.stdout.write(f"📈 Current data rows: {info['data_rows']}")
                    self.stdout.write(f"📏 Sheet dimensions: {info['row_count']}x{info['col_count']}")
                
                # Write single test profile if requested
                if options['write_test']:
                    self.stdout.write("✏️ Writing single test profile...")
                    test_profile = {
                        "full_name": f"Test User {int(time.time())}",
                        "position": "Software Engineer",
                        "company_name": "Test Company",
                        "email": "test@example.com",
                        "profile_url": "https://linkedin.com/in/testuser"
                    }
                    
                    if exporter.write_profile(test_profile):
                        self.stdout.write(self.style.SUCCESS("✅ Test profile written successfully"))
                    else:
                        self.stdout.write(self.style.ERROR("❌ Failed to write test profile"))
                
                # Write batch test profiles if requested
                if options['batch_test']:
                    self.stdout.write("📦 Writing batch test profiles...")
                    test_profiles = []
                    
                    for i in range(1, 6):  # 5 test profiles
                        test_profiles.append({
                            "full_name": f"Batch Test User {i}",
                            "position": f"Test Position {i}",
                            "company_name": f"Test Company {i}",
                            "email": f"batch.test{i}@example.com",
                            "profile_url": f"https://linkedin.com/in/batchtest{i}"
                        })
                    
                    try:
                        result = exporter.write_batch(test_profiles, batch_size=3)
                        if result.get('success'):
                            self.stdout.write(self.style.SUCCESS(
                                f"✅ Batch test completed: {result['count']} profiles written"
                            ))
                        else:
                            self.stdout.write(self.style.ERROR("❌ Batch test failed"))
                    except Exception as batch_error:
                        self.stdout.write(self.style.ERROR(f"❌ Batch test error: {batch_error}"))
                
                # If no specific tests requested, just show connection info
                if not options['write_test'] and not options['batch_test']:
                    self.stdout.write("💡 Use --write-test to write a single test profile")
                    self.stdout.write("💡 Use --batch-test to write 5 test profiles in batch")
            
            else:
                self.stdout.write(self.style.ERROR("❌ Google Sheets connection failed"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error testing Google Sheets: {e}"))
            import traceback
            self.stdout.write(self.style.ERROR(f"📋 Traceback: {traceback.format_exc()}"))
