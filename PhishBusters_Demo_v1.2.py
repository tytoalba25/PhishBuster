# Install dependencies with: pip install -r requirements.txt
# Run the app with: streamlit run PhishBusters_Demo_v1.2.py

import streamlit as st
import pythoncom
import win32com.client as win32
from bs4 import BeautifulSoup
import pandas as pd
import pickle

# Load pre-trained models
print("Initializing Phish Busters application...")
print("Loading vectorizer and classifier models...")
vectorizer = pickle.load(open('pickle/vectorizer.pkl', 'rb'))
classifier = pickle.load(open('pickle/classifier.pkl', 'rb'))
print("Models loaded successfully.")

# Configure Streamlit app settings
st.set_page_config(page_title="Phish Busters: AI Mailbox Scanner", layout="wide")
st.sidebar.image("images/PhishBuster.png", width=150)
st.sidebar.title("Phish Busters: AI Mailbox Scanner")

def preprocess_text(text):
    """Extracts plain text from email HTML or rich text and handles Unicode issues."""
    print("Preprocessing email text...")
    soup = BeautifulSoup(text, "html.parser")
    plain_text = soup.get_text()
    return sanitize_text(plain_text)

def sanitize_text(text):
    """Sanitizes text to handle Unicode errors."""
    try:
        # Replace invalid characters or remove them
        return text.encode("utf-8", "replace").decode("utf-8")
    except UnicodeEncodeError as e:
        print(f"UnicodeEncodeError encountered: {e}. Replacing invalid characters.")
        return text.encode("utf-8", "ignore").decode("utf-8")

def classify_email(text):
    """Classifies email content as 'Safe' or 'Unsafe'."""
    print("Classifying email...")
    clean_text = [preprocess_text(text)]
    vect = vectorizer.transform(clean_text)
    prediction = classifier.predict(vect)[0]
    print(f"Email classified as: {'Unsafe' if prediction == 1 else 'Safe'}")
    return "Unsafe" if prediction == 1 else "Safe"

def get_outlook():
    """Initializes and returns an Outlook MAPI namespace."""
    print("Initializing Outlook application...")
    pythoncom.CoInitialize()
    outlook = win32.Dispatch("Outlook.Application").GetNamespace("MAPI")
    print("Outlook initialized.")
    return outlook

def highlight_unsafe(df):
    """Highlights unsafe emails in the DataFrame."""
    print("Highlighting unsafe emails...")
    styles = pd.DataFrame(
        "background-color: lightcoral;",
        index=df.index,
        columns=df.columns
    )
    styles.loc[df["Classification"] != "Unsafe", :] = ""
    return styles

def scan_folder(mailbox, folder_name):
    """Scans a single folder and classifies emails."""
    results = []
    folder = mailbox.Folders[folder_name]
    total_emails = folder.Items.Count
    print(f"Scanning {total_emails} emails in folder: {folder_name}...")
    scanned_emails = 0

    progress = st.progress(0)

    for item in folder.Items:
        if item.Class == 43:  # Process only MailItem objects
            subject = sanitize_text(item.Subject or "No Subject")
            body = sanitize_text(item.Body or "No Body")
            classification = classify_email(body)
            partial_body = sanitize_text(body[:50] + "...") if len(body) > 50 else sanitize_text(body)
            results.append({
                "Classification": classification,
                "Date Received": item.ReceivedTime.strftime('%Y-%m-%d %H:%M:%S') if item.ReceivedTime else "Unknown",
                "Sender": sanitize_text(item.SenderName or "Unknown"),
                "Subject": subject,
                "Partial Body": partial_body
            })
            scanned_emails += 1
            progress.progress(scanned_emails / total_emails)
    print("Folder scanning complete.")
    return results

def get_mailboxes_and_folders(outlook):
    """Fetches mailboxes and their folders."""
    print("Retrieving mailboxes and folders...")
    mailboxes = [outlook.Folders.Item(i + 1).Name for i in range(outlook.Folders.Count)]
    mailbox_folders = {
        mailbox: [folder.Name for folder in outlook.Folders[mailbox].Folders]
        for mailbox in mailboxes
    }
    print(f"Mailboxes retrieved: {mailboxes}")
    return mailboxes, mailbox_folders

def main():
    """Main application function."""
    print("Launching Phish Busters...")
    outlook = get_outlook()
    mailboxes, mailbox_folders = get_mailboxes_and_folders(outlook)

    st.sidebar.header("Mail Settings")
    selected_mailbox = st.sidebar.selectbox("Select Mailbox", mailboxes)

    if selected_mailbox:
        folders = mailbox_folders[selected_mailbox]
        # Check if "Inbox" exists and set it as the default folder
        default_folder = "Inbox" if "Inbox" in folders else folders[0]
        selected_folder = st.sidebar.selectbox("Select Folder to Scan", folders, index=folders.index(default_folder))

        if st.sidebar.button("Scan Selected Folder"):
            mailbox = outlook.Folders[selected_mailbox]
            results = scan_folder(mailbox, selected_folder)

            if results:
                results_df = pd.DataFrame(results, columns=[
                    "Classification", "Date Received", "Sender", "Subject", "Partial Body"
                ])
                total_emails = len(results_df)
                unsafe_count = results_df["Classification"].value_counts().get("Unsafe", 0)
                safe_count = total_emails - unsafe_count

                st.markdown(f"""
                    ### Email Summary
                    - **Total Emails Scanned:** {total_emails}
                    - **Unsafe Emails Detected:** {unsafe_count}
                    - **Safe Emails Detected:** {safe_count}
                """)
                styled_df = results_df.style.apply(highlight_unsafe, axis=None)
                st.dataframe(styled_df, use_container_width=True)
                print(f"Summary: Total: {total_emails}, Unsafe: {unsafe_count}, Safe: {safe_count}")
            else:
                st.warning("No emails found in the selected folder.")
                print("No emails found.")

if __name__ == "__main__":
    main()
