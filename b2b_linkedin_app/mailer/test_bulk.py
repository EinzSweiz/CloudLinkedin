from mailer.tasks import send_bulk_emails

if __name__ == "__main__":
    recipients = [
        {"email": "riad.sultanov.1999@gmail.com", "name": "Riad"},
        {"email": "test@example.com", "name": "Tester"},
    ]
    subject = "Testing Bulk Emails 💥"
    template = "<h2>Hey {{name}},</h2><p>This is a webhook test!</p>"

    send_bulk_emails.delay(recipients, subject, template)