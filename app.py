# app.py

from flask import Flask, render_template, request, jsonify
from uagents import Agent, Context, Model
import asyncio
import queue
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Message Models
class AssessmentRequest(Model):
    question: str
    user_answer: str

class QuestionResponse(Model):
    question: str

# Create trigger agent
trigger_agent = Agent(
    name="web_trigger_agent",
    port=8004,
    seed="web_trigger_seed",
    endpoint=["http://127.0.0.1:8004/submit"]
)

# Store assessment agent address
ASSESSMENT_AGENT_ADDRESS = "agent1q02jjvfue5cffev8zsmzumjc28zkkh7cpvxnz36apundff8nqukqqwfx5g0"

# Queue to store the latest question
question_queue = queue.Queue()

# Global context for the trigger agent
agent_context = None

class ChatBot:
    def __init__(self):
        self.current_question = "What do you know about AI?"
        self.trigger_agent = trigger_agent
    
    async def process_message(self, user_message):
        try:
            logger.info(f"Processing message. Current question: {self.current_question}")
            logger.info(f"User response: {user_message}")
            
            # Create assessment request
            request = AssessmentRequest(
                question=self.current_question,
                user_answer=user_message
            )
            
            # Send to assessment agent
            if agent_context:
                logger.info(f"Sending request to assessment agent at {ASSESSMENT_AGENT_ADDRESS}")
                await agent_context.send(ASSESSMENT_AGENT_ADDRESS, request)
                logger.info("Request sent to assessment agent successfully")
            else:
                logger.error("Agent context not initialized")
                return {"question": "System is not ready. Please try again."}
            
            # Wait for new question
            try:
                logger.info("Waiting for new question from question generator...")
                new_question = question_queue.get(timeout=5)
                logger.info(f"Received new question: {new_question}")
                self.current_question = new_question
                return {"question": new_question}
            except queue.Empty:
                logger.warning("Timeout waiting for new question")
                return {"question": "Could you elaborate more on that?"}
            
        except Exception as e:
            logger.error(f"Error in process_message: {e}", exc_info=True)
            return {"question": "I didn't quite catch that. Could you try again?"}
    
    def reset_conversation(self):
        self.current_question = "What do you know about AI?"
        # Clear the question queue
        while not question_queue.empty():
            question_queue.get()

# Initialize chatbot
chatbot = ChatBot()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    logger.info(f"Received chat request with message: {user_message}")
    response = asyncio.run(chatbot.process_message(user_message))
    logger.info(f"Sending response: {response}")
    return jsonify(response)

@app.route('/reset', methods=['POST'])
def reset():
    chatbot.reset_conversation()
    return jsonify({"status": "success"})

# Handle incoming questions from question generator
@trigger_agent.on_message(model=QuestionResponse)
async def handle_new_question(ctx: Context, sender: str, msg: QuestionResponse):
    logger.info(f"Received question from generator: {msg.question}")
    question_queue.put(msg.question)

# Run trigger agent in background and store its context
@trigger_agent.on_event("startup")
async def startup(ctx: Context):
    global agent_context
    agent_context = ctx
    logger.info("Web trigger agent started")
    logger.info(f"Trigger agent address: {ctx.address}")

if __name__ == '__main__':
    # Start the trigger agent in background
    import threading
    agent_thread = threading.Thread(target=lambda: trigger_agent.run())
    agent_thread.daemon = True
    agent_thread.start()
    
    # Run Flask app
    app.run(debug=True)