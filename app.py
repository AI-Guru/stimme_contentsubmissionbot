import os
import gradio as gr
from fastapi import FastAPI
from enum import Enum
import time
import logging
import uuid
from langchain_core.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


# Configuration.
#model = "gemma2:9b"
model = "gemma2:27b"
#model = "llama3.2-vision"
default_user_input = "In Heilbronn hat ein Würzburger die Tauben gefüttert."
default_user_input = ""

#ollama_host = "http://host.docker.internal:11434"
ollama_host = "http://localhost:11434"

# The state space for the FSM as an enum.
class ConversationState(int, Enum):
    BEGIN = 0
    CHECK_FOR_MORE = 1
    WRITE_ARTICLE = 2
    DONE = 3


class Application:
    """
    The main application class.
    Here we define the user interface and the state machine.    
    """

    def __init__(self, development=False):
        self._main_window = None
        self.logger = self.create_logger()
        self.initialize()
        self.logger.info("Application initialized.")
        self.output_path = "articles"
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
 

    def create_logger(self):
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
    

    def initialize(self):

        # Initialize the chat messages.
        self.chat_messages = []
        self.article_messages = []
        self.article = ""

        # Initialize the state machine.
        self.state = ConversationState.BEGIN
        self.time_in_steps = 0
        self.run_state_machine()


    def build_interface(self):

        # CSS to deacivate the footer.
        css = "footer {visibility: hidden}"

        # Create the main window.
        with gr.Blocks(theme=gr.themes.Soft(), css=css) as self.demo:

            # Add the logos.
            with open("assets/stimme.svg", "r") as file:
                svg_content_1 = file.read()
            with open("assets/42.svg", "r") as file:
                svg_content_2 = file.read()
            with open("assets/header.html", "r") as file:
                html_content = file.read().format(svg_content_1=svg_content_1, svg_content_2=svg_content_2)
            gr.HTML(html_content)

            # Add the main column.
            with gr.Column() as self.main_column:

                # Add the chatbot.
                self.chat_bot = gr.Chatbot(type="messages", show_label=False, value=self.chat_messages)
                
                # Add the text box for user input and the send button.
                self.text_box = gr.Textbox(label=None, show_label=False, lines=5, placeholder="Enter text here", value=default_user_input)
                send_button = gr.Button("Send")

            # Add the article column.
            # This will be hidden until the article is ready.
            with gr.Column(visible=False) as self.article_column:
                gr.Markdown("## Danke für die Informationen! Hier ist der Artikel:")

                # Add horizontal line.
                gr.HTML("<hr>")

                # Add a text box for the article.
                self.article_text_box = gr.Markdown(label=None, show_label=False, value="")

                # Add a horizontal line.
                gr.HTML("<hr>")

                gr.Markdown("Der Artikel wurde gespeichert und steht ab jetzt unseren Redakteuren zur Verfügung.")

                # Add restart button.
                restart_button = gr.Button("Restart")

            # Add a footer.
            with open("assets/footer.html", "r") as file:
                footer_content = file.read()
            gr.HTML(footer_content)

            # Add the handlers.
            send_button.click(
                self.on_send_click,
                inputs=[self.text_box],
                outputs=[self.chat_bot, self.text_box, self.article_text_box, self.main_column, self.article_column]
            )
            self.text_box.submit(
                self.on_send_click,
                inputs=[self.text_box],
                outputs=[self.chat_bot, self.text_box, self.article_text_box, self.main_column, self.article_column]
            )

            # Make the main column invisible when the reset button is clicked.
            restart_button.click(
                self.on_restart_click,
                inputs=[],
                outputs=[self.chat_bot, self.main_column, self.article_column]
            )


    def on_restart_click(self):
        self.initialize()
        return self.chat_messages, gr.update(visible=True), gr.update(visible=False)


    def on_send_click(self, user_input):

        if user_input.strip() == "":
            return self.chat_messages, "", "", gr.update(visible=True), gr.update(visible=False)

        # Add the user message to the chat.
        self.add_chat_message("user", user_input, is_article_message=True)

        # Run the state machine.
        self.run_state_machine()

        # Handle the end.
        article_text = ""   
        main_column_visible = True
        article_column_visible = False
        if self.state == ConversationState.DONE:
            article_text = self.article
            main_column_visible = False
            article_column_visible = True

        # Return the chat messages.
        return self.chat_messages, "", article_text, gr.update(visible=main_column_visible), gr.update(visible=article_column_visible)


    def run_state_machine(self):

        # Increment the time in the current step.
        self.time_in_steps += 1

        # Begin state, or initial state.
        if self.state == ConversationState.BEGIN:

            # Do the welcome message.
            template = HumanMessagePromptTemplate.from_template_file("prompttemplates/welcome.txt", input_variables=[])
            message = template.format().content
            self.add_chat_message("assistant", message)
            
            # Do the what message.
            template = HumanMessagePromptTemplate.from_template_file("prompttemplates/what.txt", input_variables=[])
            message = template.format().content
            self.add_chat_message("assistant", message)

            # Move to the next state.
            self.state = ConversationState.CHECK_FOR_MORE
            self.time_in_steps = 0

        # Check for more state.
        elif self.state == ConversationState.CHECK_FOR_MORE:

            dialogue = self.get_dialogue()

            system_message = SystemMessagePromptTemplate.from_template_file("prompttemplates/system.txt", input_variables=[])
            system_message = system_message.format()

            human_message = HumanMessagePromptTemplate.from_template_file("prompttemplates/refinement.txt", input_variables=["user_texts"])
            human_message = human_message.format(user_texts=dialogue, steps=self.time_in_steps)

            text = self.invoke_model(system_message, human_message)

            # Check if we are done.
            if "TASK DONE" in text:
                
                # Go to write article.
                self.state = ConversationState.WRITE_ARTICLE
                self.time_in_steps = 0
                self.run_state_machine()

            # Not done yet.
            else:
                self.add_chat_message("assistant", text, is_article_message=True)

        # Write article state.
        elif self.state == ConversationState.WRITE_ARTICLE:

            text = "Okay, ich schreibe den Artikel..."
            self.add_chat_message("assistant", text)

            text = self.write_article()
            self.article = text
            self.add_chat_message("assistant", text)

            # Put the text in a file.
            self.logger.info("Writing article to file...")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}.txt"
            article_path = os.path.join(self.output_path, filename)
            with open(article_path, "w") as file:
                file.write(text)
                file.write("\n")
                file.write("Relevant messages:")
                file.write("\n")
                file.write(self.get_dialogue(article_messages_only=True))
                file.write("\n")
                file.write("All messages:")
                file.write("\n")
                file.write(self.get_dialogue(article_messages_only=False))
                self.logger.info(f"Article written to {article_path}")

            # Done.
            self.state = ConversationState.DONE
            
        # Done state.
        elif self.state == ConversationState.DONE:
            pass
        
        # Invalid state.
        else:
            raise ValueError(f"Invalid state: {self.state}")
        

    def refinement(self):

        dialogue = self.get_dialogue()

        system_message = SystemMessagePromptTemplate.from_template_file("prompttemplates/system.txt", input_variables=[])
        system_message = system_message.format()

        human_message = HumanMessagePromptTemplate.from_template_file("prompttemplates/refinement.txt", input_variables=["user_texts"])
        human_message = human_message.format(user_texts=dialogue, steps=self.time_in_steps)

        text = self.invoke_model(system_message, human_message)
        return text
    

    def get_dialogue(self, article_messages_only=False):
        dialogue = ""
        if article_messages_only:
            messages = self.article_messages
        else:
            messages = self.chat_messages
        for message in messages:
            dialogue += f"{message['role']}: {message['content']}\n"
        return dialogue
    

    def write_article(self):

        # Get all the human messages.
        dialogue = self.get_dialogue(article_messages_only=True)

        # Get the date as DD.MM.YYYY.
        date = time.strftime("%d.%m.%Y")

        system_message = SystemMessagePromptTemplate.from_template_file("prompttemplates/system.txt", input_variables=[])
        system_message = system_message.format()

        human_message = HumanMessagePromptTemplate.from_template_file("prompttemplates/writearticle.txt", input_variables=["user_texts", "date"])
        human_message = human_message.format(user_texts=dialogue, date=date)

        text = self.invoke_model(system_message, human_message)
        return text
     

    def invoke_model(self, system_message, human_message):
        self.logger.info(f"System message: {system_message}")
        self.logger.info(f"Human message: {human_message}")
        llm = ChatOllama(
            base_url=ollama_host,
            model=model
        )
        prompt = ChatPromptTemplate.from_messages([system_message, human_message])
        chain = prompt | llm | StrOutputParser()
        text = chain.invoke({})
        self.logger.info(f"Model response: {text}")
        return text


    def add_chat_message(self, role, content, is_article_message=False):
        assert role in ["user", "assistant"], f"Invalid role: {role}"
        new_message = {"role": role, "content": content}
        self.chat_messages.append(new_message)
        if is_article_message:
            self.article_messages.append(new_message)



# FastAPI and Gradio integration
fast_api_app = FastAPI()

# Initialize Gradio
gradio_app = Application(development=True)  # Create an instance of the GradioApp class
gradio_app.build_interface()  # Build the interface

# Mount Gradio app onto FastAPI
app = gr.mount_gradio_app(fast_api_app, gradio_app.demo, path="/")