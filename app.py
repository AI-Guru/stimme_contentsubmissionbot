import os
import gradio as gr
from fastapi import FastAPI
from enum import Enum
import time
from langchain_core.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


# Configuration.
#model = "gemma2:9b"
model = "gemma2:27b"


default_user_input = "In Heilbronn hat ein Würzburger die Tauben gefüttert."


# The state space for the FSM as an enum.
class ConversationState(int, Enum):
    BEGIN = 0
    CHECK_FOR_MORE = 1
    WRITE_ARTICLE = 2


class Application:

    def __init__(self, development=False):
        self._main_window = None
        self.chat_messages = []
        self.article_messages = []

        self.state = ConversationState.BEGIN
        self.time_in_steps = 0
        self.run_state_machine()


    def build_interface(self):

        # Create the main window.
        with gr.Blocks(theme=gr.themes.Soft()) as self.demo:

            # Add the logos.
            with open("assets/stimme.svg", "r") as file:
                svg_content_1 = file.read()
            with open("assets/42.svg", "r") as file:
                svg_content_2 = file.read()
            html_content = f"""
            <div style="display: flex; height: 50pt; width: 100%;">
                <div style="flex: 1; background-color: #0085c2; display: flex; align-items: center; justify-content: center; padding: 5pt;">
                    <div style="height: 90%; width: 90%; display: flex; align-items: center; justify-content: center;">
                        <svg style="height: 100%; width: 100%; object-fit: contain; margin: auto;">{svg_content_1}</svg>
                    </div>
                </div>
                <div style="flex: 1; background-color: #ffffff; display: flex; align-items: center; justify-content: center; padding: 5pt;">
                    <div style="height: 90%; width: 90%; display: flex; align-items: center; justify-content: center;">
                        <svg style="height: 100%; width: 100%; object-fit: contain; margin: auto;">{svg_content_2}</svg>
                    </div>
                </div>
            </div>
            """
            gr.HTML(html_content)

            # Add the chatbot.
            self.chat_bot = gr.Chatbot(type="messages", show_label=False, value=self.chat_messages)
            
            # Add the text box for user input and the send button.
            self.text_box = gr.Textbox(label=None, show_label=False, lines=5, placeholder="Enter text here", value=default_user_input)
            send_button = gr.Button("Send")

            # Add the handlers.
            send_button.click(
                self.on_send_click,
                inputs=[self.text_box],
                outputs=[self.chat_bot, self.text_box]
            )
            self.text_box.submit(
                self.on_send_click,
                inputs=[self.text_box],
                outputs=[self.chat_bot, self.text_box]
            )
        

    def on_send_click(self, user_input):

        # Add the user message to the chat.
        self.add_chat_message("user", user_input, is_article_message=True)

        # Run the state machine.
        self.run_state_machine()

        # Return the chat messages.
        return self.chat_messages, ""


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
            self.add_chat_message("assistant", text)

            # Put the text in a file.
            print("Writing article to file...")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}.txt"
            article_path = os.path.join("articles", filename)
            if not os.path.exists("articles"):
                os.makedirs("articles")
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
                print(f"Article written to {article_path}")


        # Invalid state.
        else:
            raise ValueError(f"Invalid state: {self.state}")
        

    def refinement(self):

        # Get all the human messages.
        #human_messages = [message["content"] for message in st.session_state.messages if message["role"] == "user"]
        #user_texts = "\n\n".join(human_messages)

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
        print("System message:", system_message)
        print("Human message:", human_message)
        llm = ChatOllama(model=model)
        prompt = ChatPromptTemplate.from_messages([system_message, human_message])
        chain = prompt | llm | StrOutputParser()
        text = chain.invoke({})
        print("Model response:", text)
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