# streamlit run PhisBusters_Demo_v1.0.py 

# https://www.sciencedirect.com/science/article/pii/S1877050921011741


import win32com.client  # For Outlook integration
import pythoncom  # Required for COM initialization
import streamlit as st  # For building the web application
import pandas as pd  # For data manipulation
import pickle  # For loading the pre-trained models
from nltk.stem import WordNetLemmatizer  # For text preprocessing
from nltk.corpus import stopwords  # For removing stopwords
from textblob import TextBlob  # For basic NLP operations
import nltk

# Download NLTK stopwords
nltk.download('stopwords')

# Initialize stopwords and lemmatizer
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

# Define a text preprocessing function
def preprocess_text(text):
    """
    Preprocesses the input text for model prediction.
    
    Steps:
    1. Converts text to lowercase.
    2. Tokenizes text into words.
    3. Removes non-alphabetic tokens and stopwords.
    4. Applies lemmatization to standardize words.

    Args:
        text (str): Raw email text.

    Returns:
        str: Cleaned and preprocessed text.
    """
    blob = TextBlob(text)
    words = [word.lower() for word in blob.words if word.isalpha()]
    words = [word for word in words if word not in stop_words]
    words = [lemmatizer.lemmatize(word) for word in words]
    return ' '.join(words)

# Load the vectorizer and classifier models
@st.cache_resource
def load_models():
    """
    Loads the pre-trained vectorizer and classifier models from pickle files.

    Returns:
        tuple: A tuple containing the vectorizer and classifier models.
    """
    try:
        vectorizer = pickle.load(open("pickle/vectorizer.pkl", "rb"))
        classifier = pickle.load(open("pickle/classifier.pkl", "rb"))
        st.success("Models loaded successfully!")
        return vectorizer, classifier
    except Exception as e:
        st.error(f"Failed to load models: {e}")
        return None, None

# Load models
vectorizer, classifier = load_models()

# Function to connect to the specified Outlook mailbox
def connect_to_mailbox(mailbox_name):
    """
    Connects to the specified Outlook mailbox.

    Args:
        mailbox_name (str): The name of the Outlook mailbox to connect to.

    Returns:
        object: Outlook mailbox account object if successful, otherwise None.
    """
    try:
        # Initialize COM for Windows
        pythoncom.CoInitialize()

        # Access the Outlook namespace
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

        # Find the mailbox by name
        target_account = None
        for account in outlook.Folders:
            if account.Name == mailbox_name:
                target_account = account
                break

        if not target_account:
            raise Exception(f"Account '{mailbox_name}' not found.")

        return target_account  # Return the account folder
    except Exception as e:
        st.error(f"Failed to connect to mailbox: {e}")
        return None

# Function to fetch emails from the Inbox folder
def fetch_emails_from_mailbox(account, max_emails=100):
    """
    Fetches emails from the Inbox folder of the specified mailbox account.

    Args:
        account (object): The Outlook mailbox account object.
        max_emails (int): The maximum number of emails to fetch.

    Returns:
        pd.DataFrame: A DataFrame containing the fetched email data.
    """
    try:
        emails = []
        progress_bar = st.progress(0)  # Initialize progress bar

        # Access the Inbox folder
        inbox = account.Folders["Inbox"]
        messages = inbox.Items

        # Fetch emails up to the specified limit
        email_count = 0
        for message in messages:
            if email_count >= max_emails:
                break
            try:
                body = message.Body or ""  # Ensure email body is not None
                emails.append({
                    "Folder": "Inbox",
                    "Subject": message.Subject or "No Subject",
                    "Sender": message.SenderName or "Unknown Sender",
                    "Body": body
                })
                email_count += 1
                progress_bar.progress(email_count / max_emails)  # Update progress bar
            except Exception as e:
                st.warning(f"Could not fetch email: {e}")

        progress_bar.empty()  # Remove the progress bar
        return pd.DataFrame(emails)

    except Exception as e:
        st.error(f"Failed to fetch emails: {e}")
        return pd.DataFrame()

# Function to scan emails using the phishing detection model
def scan_emails(emails_df):
    """
    Scans emails for phishing using the pre-trained classifier model.

    Args:
        emails_df (pd.DataFrame): DataFrame containing email data.

    Returns:
        pd.DataFrame: Updated DataFrame with phishing classifications.
    """
    if emails_df.empty:
        st.warning("No emails to scan.")
        return emails_df

    # Ensure email bodies are strings
    emails_df["Body"] = emails_df["Body"].astype(str)

    # Initialize progress bar
    progress_bar = st.progress(0)
    processed_texts = []

    # Preprocess and classify emails
    for index, email_body in enumerate(emails_df["Body"]):
        # Preprocess email body
        processed_text = preprocess_text(email_body)
        processed_texts.append(processed_text)

        # Update progress bar
        progress_bar.progress((index + 1) / len(emails_df))

    # Vectorize preprocessed texts and predict classifications
    vectors = vectorizer.transform(processed_texts)
    predictions = classifier.predict(vectors)

    # Add predictions to the DataFrame
    emails_df["Classification"] = ["Phishing" if p == 1 else "Legitimate" for p in predictions]

    # Remove progress bar
    progress_bar.empty()

    # Reorder columns to display Classification first
    columns = ["Classification"] + [col for col in emails_df.columns if col != "Classification"]
    return emails_df[columns]

# Function to style phishing emails
def highlight_phishing(row):
    """
    Highlights phishing emails in red for better visibility in the UI.

    Args:
        row (pd.Series): A row of the DataFrame.

    Returns:
        list: A list of style strings for each column in the row.
    """
    if row["Classification"] == "Phishing":
        return ["background-color: red; color: white"] * len(row)
    else:
        return [""] * len(row)

# Streamlit App UI
st.title("Phish Busters: AI Mailbox Scanner with NLP Model")
st.write("Scan your entire Outlook mailbox for potential phishing emails.")

# Initialize session state for emails and results
if "emails_df" not in st.session_state:
    st.session_state["emails_df"] = None
if "scanned_emails_df" not in st.session_state:
    st.session_state["scanned_emails_df"] = None

# User input for mailbox name and number of emails to fetch
mailbox_name = st.text_input("Enter your mailbox name (e.g., your_email@domain.com):")
max_emails = st.number_input(
    "Enter the number of emails to fetch:", min_value=1, max_value=1000, value=100
)

# Button to fetch emails
if st.button("Connect and Fetch Emails"):
    account = connect_to_mailbox(mailbox_name)
    if account:
        st.success(f"Connected to mailbox: {mailbox_name}")
        emails_df = fetch_emails_from_mailbox(account, max_emails=max_emails)  # Fetch emails
        if not emails_df.empty:
            st.session_state["emails_df"] = emails_df  # Save fetched emails in session state
            st.session_state["scanned_emails_df"] = None  # Reset scan results when fetching new emails
        else:
            st.error("No emails found in the mailbox.")

# Display fetched emails only if they exist in session state
if st.session_state["emails_df"] is not None:
    st.write("Fetched Emails:")
    st.dataframe(st.session_state["emails_df"])

    # Button to scan emails
    if st.button("Scan Emails for Phishing"):
        scanned_emails_df = scan_emails(st.session_state["emails_df"])
        st.session_state["scanned_emails_df"] = scanned_emails_df  # Save scan results in session state

# Display scan results only if they exist in session state
if st.session_state["scanned_emails_df"] is not None:
    st.write("Scan Results:")

    # Highlight phishing emails
    styled_df = st.session_state["scanned_emails_df"].style.apply(highlight_phishing, axis=1)
    st.dataframe(styled_df)
