import sqlite3
import hashlib
import time
import random
import smtplib
from email.message import EmailMessage
from database import DB_FILE

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_manager_login(email, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM managers WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    
    if row:
        stored_hash = row[0]
        if stored_hash == hash_password(password):
            return True
    return False

def check_manager_exists(email):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM managers WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row is not None

def generate_and_send_otp(manager_email, sender_email, app_password):
    """
    Generates a 6-digit OTP, stores it with a 5-minute expiry, and sends the email.
    """
    if not check_manager_exists(manager_email):
        return False, "Manager email not found in the system."
        
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    expiry_time = time.time() + (5 * 60) # 5 minutes from now
    
    # Update Database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE managers 
        SET otp=?, otp_expiry=?, failed_attempts=0 
        WHERE email=?
    ''', (otp, expiry_time, manager_email))
    conn.commit()
    conn.close()
    
    # Send Email
    try:
        msg = EmailMessage()
        msg['Subject'] = "Digital Measurement Book Password Reset"
        msg['From'] = sender_email
        msg['To'] = manager_email
        
        body = f"""Hello Manager,

We received a request to reset your password.

Your verification code is: {otp}

This code will expire in 5 minutes.

If you did not request this, please ignore this email.

Digital Measurement Book System"""

        msg.set_content(body)
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            
        return True, "Verification code sent to email."
    except Exception as e:
        return False, f"Email sending failed: {str(e)}"

def verify_otp(email, entered_otp):
    """
    Verifies the OTP against the database, enforcing expiry and 3 maximum attempts.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT otp, otp_expiry, failed_attempts FROM managers WHERE email=?", (email,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return False, "User not found."
        
    stored_otp, expiry_time, failed_attempts = row
    
    if failed_attempts >= 3:
        conn.close()
        return False, "Maximum attempts reached. Please request a new OTP."
        
    if time.time() > expiry_time:
        conn.close()
        return False, "OTP has expired. Please request a new code."
        
    if entered_otp == stored_otp:
        # Success, reset attempts but do NOT erase OTP yet (let reset_password do it)
        c.execute("UPDATE managers SET failed_attempts=0 WHERE email=?", (email,))
        conn.commit()
        conn.close()
        return True, "OTP Verified."
    else:
        # Failure
        failed_attempts += 1
        c.execute("UPDATE managers SET failed_attempts=? WHERE email=?", (failed_attempts, email))
        conn.commit()
        conn.close()
        return False, f"Invalid verification code. {3 - failed_attempts} attempts remaining."

def reset_password(email, new_password):
    """
    Updates the password hash and invalidates the previous OTP.
    """
    new_hash = hash_password(new_password)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE managers 
        SET password_hash=?, otp=NULL, otp_expiry=0, failed_attempts=0 
        WHERE email=?
    ''', (new_hash, email))
    conn.commit()
    conn.close()
    return True
