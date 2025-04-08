import os
import gradio as gr
from fastapi import FastAPI
from enum import Enum
import time
import logging
import uuid
#import ollama
from ollama import Client
from langchain_core.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


# Configuration.
if "MODEL" in os.environ:
    model = os.environ["MODEL"]
else:
    model = "gemma2:27b"

if "OLLAMA_HOST" in os.environ:
    ollama_host = os.environ["OLLAMA_HOST"]
else:
    ollama_host = "http://host.docker.internal:11434"

# The state space for the FSM as an enum.
class ConversationState(int, Enum):
    BEGIN = 0
    CHECK_FOR_MORE = 1
    WRITE_ARTICLE = 2
    DONE = 3


# Create a logger
def create_logger():
    uuid_str = str(uuid.uuid4())
    logger = logging.getLogger(uuid_str)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(f"gradio.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

logger = create_logger()
output_path = "articles"
if not os.path.exists(output_path):
    os.makedirs(output_path)

# Load assets
with open("assets/stimme.svg", "r") as file:
    svg_content_1 = file.read()
with open("assets/42.svg", "r") as file:
    svg_content_2 = file.read()
with open("assets/header.html", "r") as file:
    header_content = file.read().format(svg_content_1=svg_content_1, svg_content_2=svg_content_2)
with open("assets/footer.html", "r") as file:
    footer_content = file.read()

# Load the model.
logger.info(f"Loading model {model} from {ollama_host}")
client = Client(
  host=ollama_host,
)
client.pull(model)
logger.info(f"Model {model} loaded from {ollama_host}")


# CSS for styling
css = 'footer {visibility: hidden} #chatbox [title="Clear"] {display: none} @font-face { font-family:"NNStimmeGotesk Bold";src: url("https://www.stimme-mediengruppe.de/wp-content/uploads/2021/09/NNStimmeGrotesk-Bold.woff2") format("woff2"),url("https://www.stimme-mediengruppe.de/wp-content/uploads/2021/09/NNStimmeGrotesk-Bold.woff") format("woff");font-weight: normal;font-style: normal;font-display: block;} @font-face {font-family: "NNStimmeGotesk Normal";src: url("https://www.stimme-mediengruppe.de/wp-content/uploads/2021/09/NNStimmeGrotesk-Normal.woff2") format("woff2"),url("https://www.stimme-mediengruppe.de/wp-content/uploads/2021/09/NNStimmeGrotesk-Normal.woff") format("woff");font-weight: normal;font-style: normal;font-display: block;}*{font-family: "NNStimmeGotesk Normal";} button{font-family: "NNStimmeGotesk Bold";}'


def invoke_model(system_message, human_message):
    logger.info(f"System message: {system_message}")
    logger.info(f"Human message: {human_message}")
    llm = ChatOllama(
        base_url=ollama_host,
        model=model
    )
    prompt = ChatPromptTemplate.from_messages([system_message, human_message])
    chain = prompt | llm | StrOutputParser()
    text = chain.invoke({})
    logger.info(f"Model response: {text}")
    return text


def get_dialogue(messages, article_messages_only=False):
    dialogue = ""
    for message in messages:
        dialogue += f"{message['role']}: {message['content']}\n"
    return dialogue


def write_article(article_messages):
    # Get all the human messages.
    dialogue = get_dialogue(article_messages)

    # Get the date as DD.MM.YYYY.
    date = time.strftime("%d.%m.%Y %H:%M Uhr")

    system_message = SystemMessagePromptTemplate.from_template_file("prompttemplates/system.txt", input_variables=[])
    system_message = system_message.format()

    human_message = HumanMessagePromptTemplate.from_template_file("prompttemplates/writearticle.txt", input_variables=["user_texts", "date"])
    human_message = human_message.format(user_texts=dialogue, date=date)

    text = invoke_model(system_message, human_message)
    return text, date


def save_article(article_text, all_messages, article_messages, date):
    # Put the text in a file.
    logger.info("Writing article to file...")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}.txt"
    article_path = os.path.join(output_path, filename)
    with open(article_path, "w") as file:
        file.write("-" * 20 + " ARTICLE " + "-" * 20)
        file.write("\n")
        file.write(article_text)
        file.write("\n")
        file.write("-" * 20 + " END OF ARTICLE " + "-" * 20)
        file.write("\n")
        file.write("Relevant messages:")
        file.write("\n")
        file.write(get_dialogue(article_messages))
        file.write("\n")
        file.write("All messages:")
        file.write("\n")
        file.write(get_dialogue(all_messages))
        logger.info(f"Article written to {article_path}")
    return filename


# State management for each session
def build_interface():
    with gr.Blocks(theme=gr.themes.Soft(), css=css) as demo:
        # Session state variables
        state = gr.State(value={"state": ConversationState.BEGIN, "time_in_steps": 0, 
                                "chat_messages": [], "article_messages": [], "article": ""})
        
        # Header
        gr.HTML(header_content)
        
        # Main interaction area
        with gr.Column(visible=True) as main_column:
            chat_bot = gr.Chatbot(type="messages", show_label=False, elem_id="chatbox", value=[])
            text_box = gr.Textbox(label=None, show_label=False, lines=5, placeholder="Sende eine Nachricht an Kim", value="")
            send_button = gr.Button("Senden")
        
        # Article display area (hidden initially)
        with gr.Column(visible=False) as article_column:
            gr.Markdown("## Danke für die Informationen! Hier ist der Artikel:")
            gr.HTML("<hr>")
            article_text_box = gr.Markdown(label=None, show_label=False, value="")
            gr.HTML("<hr>")
            gr.Markdown("Der Artikel wurde gespeichert und steht ab jetzt unseren Redakteuren zur Verfügung.")
            restart_button = gr.Button("Neu beginnen")
        
        # Footer
        gr.HTML(footer_content)
        
        # Initialize the conversation when the page loads
        def init_conversation(session_state):
            # Reset session state
            session_state = {
                "state": ConversationState.BEGIN,
                "time_in_steps": 0,
                "chat_messages": [],
                "article_messages": [],
                "article": ""
            }
            
            # Load welcome messages
            template = HumanMessagePromptTemplate.from_template_file("prompttemplates/welcome.txt", input_variables=[])
            welcome_message = template.format().content
            
            template = HumanMessagePromptTemplate.from_template_file("prompttemplates/what.txt", input_variables=[])
            what_message = template.format().content
            
            # Add messages to state
            session_state["chat_messages"].append({"role": "assistant", "content": welcome_message})
            session_state["chat_messages"].append({"role": "assistant", "content": what_message})
            
            # Update state
            session_state["state"] = ConversationState.CHECK_FOR_MORE
            
            return session_state, session_state["chat_messages"]
        
        # Run at page load
        demo.load(init_conversation, inputs=[state], outputs=[state, chat_bot])
        
        # Handle user message
        def on_send_click(user_input, session_state):
            # Skip empty messages
            if user_input.strip() == "":
                return session_state, session_state["chat_messages"], "", gr.update(visible=True), gr.update(visible=False)
            
            # Add user message
            session_state["chat_messages"].append({"role": "user", "content": user_input})
            session_state["article_messages"].append({"role": "user", "content": user_input})
            
            # Process according to state
            logger.info(f"Current state: {session_state['state']}")
            if session_state["state"] == ConversationState.CHECK_FOR_MORE:
                # Increment time in steps
                session_state["time_in_steps"] += 1
                
                # Process dialogue
                dialogue = get_dialogue(session_state["chat_messages"])
                
                system_message = SystemMessagePromptTemplate.from_template_file("prompttemplates/system.txt", input_variables=[])
                system_message = system_message.format()
                
                human_message = HumanMessagePromptTemplate.from_template_file("prompttemplates/refinement.txt", input_variables=["user_texts"])
                human_message = human_message.format(user_texts=dialogue, steps=session_state["time_in_steps"])
                
                response_text = invoke_model(system_message, human_message)
                
                # Check if we're ready to write the article
                if "TASK DONE" in response_text:
                    # Move to write article state
                    session_state["state"] = ConversationState.WRITE_ARTICLE
                    
                    # Add intermediate message
                    writing_message = "Okay, ich schreibe den Artikel..."
                    session_state["chat_messages"].append({"role": "assistant", "content": writing_message})
                    
                    # Write the article
                    article_text, date = write_article(session_state["article_messages"])
                    session_state["article"] = article_text
                    
                    # Save the article
                    filename = save_article(article_text, session_state["chat_messages"], 
                                            session_state["article_messages"], date)
                    
                    # Add article to chat
                    session_state["chat_messages"].append({"role": "assistant", "content": article_text})
                    
                    # Move to done state
                    session_state["state"] = ConversationState.DONE
                    
                    # Show the article column
                    return (session_state, session_state["chat_messages"], article_text, 
                            gr.update(visible=False), gr.update(visible=True))
                else:
                    # Add assistant response
                    session_state["chat_messages"].append({"role": "assistant", "content": response_text})
                    session_state["article_messages"].append({"role": "assistant", "content": response_text})
            
            # Return updated state and UI
            return (session_state, session_state["chat_messages"], "", 
                    gr.update(visible=True), gr.update(visible=False))
        
        # Handle restart button
        def on_restart_click(session_state):
            # Reset session state
            new_state, messages = init_conversation(session_state)
            # Switch back to main view
            return new_state, messages, gr.update(visible=True), gr.update(visible=False)
        
        # Connect event handlers
        send_button.click(
            on_send_click,
            inputs=[text_box, state],
            outputs=[state, chat_bot, article_text_box, main_column, article_column]
        )
        text_box.submit(
            on_send_click,
            inputs=[text_box, state],
            outputs=[state, chat_bot, article_text_box, main_column, article_column]
        )
        restart_button.click(
            on_restart_click,
            inputs=[state],
            outputs=[state, chat_bot, main_column, article_column]
        )
        
        # Clear the text box after sending
        def clear_textbox():
            return ""
        send_button.click(clear_textbox, outputs=[text_box])
        text_box.submit(clear_textbox, outputs=[text_box])
    
    return demo


# FastAPI and Gradio integration
fast_api_app = FastAPI()

@fast_api_app.get("/healthcheck")
async def healthcheck():
    return {"status": "healthy"}

# Build and mount the interface
demo = build_interface()
app = gr.mount_gradio_app(fast_api_app, demo, path="/", app_kwargs={"default_queue": True})