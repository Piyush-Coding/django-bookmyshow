import logging
import datetime
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

# Initialize logger configured in settings.py
logger = logging.getLogger('bookings')

@shared_task(bind=True, max_retries=3)
def send_booking_confirmation_email(self, booking_ids, recipient_email, payment_id=None, total_amount=None):
    """
    Asynchronously sends a movie booking confirmation HTML email to the user.
    Retries up to 3 times with exponential backoff if sending fails.
    """
    # Import locally within the task to prevent circular dependencies / early loading issues
    from movies.models import Booking
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    booking_ids_str = ", ".join(str(bid) for bid in booking_ids)
    
    logger.info(
        f"Attempting to send booking confirmation email. "
        f"Booking ID(s): [{booking_ids_str}], Recipient: {recipient_email}, "
        f"Payment ID: {payment_id or 'N/A'}, Timestamp: {timestamp}"
    )
    
    try:
        # Retrieve all Booking records with optimized database queries
        bookings = list(Booking.objects.filter(id__in=booking_ids).select_related('movie', 'theater', 'seat', 'user'))
        
        if not bookings:
            logger.error(
                f"Booking retrieval failed. No bookings found for IDs: [{booking_ids_str}]. "
                f"Recipient: {recipient_email}, Timestamp: {timestamp}"
            )
            return f"No bookings found for IDs: {booking_ids}"
            
        first_booking = bookings[0]
        username = first_booking.user.username
        movie_name = first_booking.movie.name
        theater_name = first_booking.theater.name
        show_time = first_booking.theater.time
        
        # Format show date and show time
        show_date_str = show_time.strftime('%A, %B %d, %Y')
        show_time_str = show_time.strftime('%I:%M %p')
        
        # Gather all seat numbers
        seat_numbers = [b.seat.seat_number for b in bookings]
        seat_numbers_str = ", ".join(seat_numbers)
        
        # Prepare context context for email rendering (free of passwords, OTPs, or payment credentials)
        context = {
            'username': username,
            'movie_name': movie_name,
            'theater_name': theater_name,
            'show_date': show_date_str,
            'show_time': show_time_str,
            'seat_numbers': seat_numbers_str,
            'booking_id': booking_ids_str,
            'payment_id': payment_id or "N/A",
            'total_amount': total_amount or "N/A",
        }
        
        # Render the HTML template
        html_content = render_to_string('emails/booking_confirmation.html', context)
        text_content = strip_tags(html_content)
        
        subject = f"Booking Confirmed: {movie_name} - {theater_name}"
        from_email = settings.DEFAULT_FROM_EMAIL or 'noreply@bookmyseat.com'
        
        # Create and send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(
            f"Email successfully sent. Booking ID(s): [{booking_ids_str}], "
            f"Recipient: {recipient_email}, Payment ID: {payment_id or 'N/A'}, "
            f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return f"Successfully sent confirmation email to {recipient_email}"
        
    except Exception as exc:
        current_retry = self.request.retries
        retry_msg = f"Retry attempt {current_retry + 1}/3"
        
        logger.warning(
            f"Failed to send booking confirmation email. {retry_msg}. "
            f"Booking ID(s): [{booking_ids_str}], Recipient: {recipient_email}, "
            f"Reason: {str(exc)}, Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if current_retry >= self.max_retries:
            logger.error(
                f"FINAL FAILURE: Max retries ({self.max_retries}) reached. Email could not be sent. "
                f"Booking ID(s): [{booking_ids_str}], Recipient: {recipient_email}, "
                f"Reason: {str(exc)}, Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            # Re-raise the final exception so it gets marked as failed in Celery broker
            raise exc
            
        # Exponential backoff delay (30s, 60s, 120s)
        countdown = (2 ** current_retry) * 30
        raise self.retry(exc=exc, countdown=countdown)
