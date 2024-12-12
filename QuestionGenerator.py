# question_generator_agent.py

import os
from dotenv import load_dotenv
from uagents import Agent, Context, Model
from anthropic import Anthropic
from datetime import datetime
from typing import Optional

# Load environment variables
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

# Constants
DEFAULT_PORT = 8000
MODEL_NAME = "claude-3-haiku-20240307"
TRIGGER_AGENT_ADDRESS = "agent1qwqwnvgzt3vgrc8vvnj5ke987rqt4qq2u9d09r9csy76v57ujr6swd58zn5"

# Define models
class LevelUpdate(Model):
    level: int

class QuestionResponse(Model):
    question: str

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Define the question generator agent
question_generator = Agent(
    name="question_generator",
    port=DEFAULT_PORT,
    seed="question_generator_seed",
    endpoint=["http://127.0.0.1:8000/submit"],
)

def get_prompt_for_level(level: int) -> str:
    """Generate appropriate prompt based on difficulty level"""
    prompts = {
        1: """Generate a beginner-friendly question that introduces basic concepts. 
             The question should be clear, straightforward, and focus on fundamental understanding.""",
        
        2: """Generate an intermediate-level question that builds on basic concepts. 
             The question should require some analysis and connection between ideas.""",
        
        3: """Generate an advanced question that requires deep understanding. 
             The question should involve complex analysis, synthesis of multiple concepts, 
             or application to novel situations."""
    }
    
    base_prompt = (
        f"You are an advanced AI tutor. {prompts.get(level, prompts[1])} "
        f"Generate a single focused question. The response should be just the question "
        f"without any additional explanation or context."
    )
    
    return base_prompt

async def generate_question(level: int, ctx: Context) -> Optional[str]:
    """Generate a question using the Anthropic API with error handling"""
    try:
        prompt = get_prompt_for_level(level)
        
        response = anthropic_client.messages.create(
            model=MODEL_NAME,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        ctx.logger.error(f"Error generating question with Anthropic API: {e}")
        return None

@question_generator.on_message(model=LevelUpdate)
async def handle_level_update(ctx: Context, sender: str, msg: LevelUpdate):
    """Handle incoming level updates and generate appropriate questions"""
    try:
        # Validate level
        level = max(1, min(3, msg.level))  # Ensure level is between 1 and 3
        
        # Generate question
        generated_question = await generate_question(level, ctx)
        
        if generated_question:
            # Log success
            ctx.logger.info(f"Generated level {level} question")
            ctx.logger.debug(f"Question: {generated_question}")
            
            # Send question to trigger agent
            await ctx.send(
                TRIGGER_AGENT_ADDRESS, 
                QuestionResponse(question=generated_question)
            )
            ctx.logger.info(f"Question sent to trigger agent")
        else:
            # Use fallback question if generation failed
            fallback_question = "Could you please explain your understanding of this topic?"
            await ctx.send(
                TRIGGER_AGENT_ADDRESS, 
                QuestionResponse(question=fallback_question)
            )
            ctx.logger.warning("Used fallback question due to generation failure")
            
    except Exception as e:
        ctx.logger.error(f"Error in handle_level_update: {e}")
        # Send fallback question in case of any error
        try:
            await ctx.send(
                TRIGGER_AGENT_ADDRESS,
                QuestionResponse(question="Could you elaborate on that further?")
            )
        except Exception as send_error:
            ctx.logger.error(f"Error sending fallback question: {send_error}")

@question_generator.on_event("startup")
async def initialize(ctx: Context):
    """Initialize the agent"""
    try:
        ctx.logger.info(f"Question Generator Agent is starting. Address: {ctx.address}")
        print(f"Question Generator Agent Address: {ctx.address}")
    except Exception as e:
        ctx.logger.error(f"Error during initialization: {e}")
        raise  # Re-raise to prevent agent from starting with incomplete initialization

@question_generator.on_event("shutdown")
async def cleanup(ctx: Context):
    """Handle cleanup tasks on agent shutdown"""
    ctx.logger.info("Question Generator Agent is shutting down")

if __name__ == "__main__":
    question_generator.run()