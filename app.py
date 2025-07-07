from flask import Flask, request, abort
import os
import google.generativeai as genai

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

app = Flask(__name__)

# --- LINE Bot Setup ---
# Get channel access token and channel secret from environment variables
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

if not channel_access_token or not channel_secret:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variables.')
    exit()

handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

# --- Gemini AI Setup ---
# Get Gemini API key from environment variables
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    print('Specify GEMINI_API_KEY as an environment variable.')
    exit()

# Configure the Gemini client
genai.configure(api_key=gemini_api_key)
# Initialize the generative model
# For a general chatbot, 'gemini-1.5-flash' is a great, fast option.
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Webhook Handler ---
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        print(f"An error occurred: {e}")
        abort(500)

    return 'OK'

# --- Message Handler ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text

    try:
        # --- Send user's message to Gemini and get the response ---
        # We add a specific instruction for the chatbot's persona.
        # This helps guide the AI to give better, more relevant answers.
        prompt = f"You are a helpful and friendly chatbot for the Ikatan Keluarga Mahasiswa FKUI (IKM FKUI). Your role is to provide information about services, activities, and resources available at IKM FKUI. Please answer the following question: {user_message}"
        
        response = model.generate_content(prompt)
        ai_response = response.text

    except Exception as e:
        app.logger.error(f"Error generating response from Gemini: {e}")
        ai_response = "Sorry, I'm having trouble connecting to my brain right now. Please try again in a moment."

    # --- Send Gemini's response back to the user on LINE ---
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ai_response)]
            )
        )

if __name__ == "__main__":
    # Use Gunicorn or another WSGI server for production
    # For local testing:
    app.run(port=5001)
