# assessment_agent.py

import os
from dotenv import load_dotenv
from uagents import Agent, Context, Model
from anthropic import Anthropic
from typing import Optional

# Load environment variables
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

# Initialize Anthropic
anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

# Constants
DEFAULT_PORT = 8001
QUESTION_GENERATOR_ADDRESS = 'agent1qvkyh2gh6k50z284ttxyuvcwz99wrgtvgpe9v32gvtz7tjqlw2mf76lvdcf'

# Define models for messages
class AssessmentRequest(Model):
    question: str
    user_answer: str

class AssessmentResponse(Model):
    level: int
    feedback: Optional[str]

class LevelUpdate(Model):
    level: int

# Define the assessment agent
assessment_agent = Agent(
    name="assessment_agent",
    port=DEFAULT_PORT,
    seed="assessment_agent_seed",
    endpoint=["http://127.0.0.1:8001/submit"],
)

def analyze_response(response_text: str) -> tuple[int, str]:
    """
    Analyzes the AI response to extract level and feedback.
    Returns tuple of (level, feedback)
    """
    try:
        # Extract just the number from the response
        level = int(response_text.strip())
        level = max(1, min(3, level))  # Ensure level is between 1 and 3
        return level, response_text
    except ValueError:
        # If we can't parse a number, default to beginner
        return 1, "Unable to determine level precisely. Defaulting to beginner level."
    except Exception as e:
        return 1, f"Error analyzing response: {str(e)}"

@assessment_agent.on_message(model=AssessmentRequest)
async def handle_assessment_request(ctx: Context, sender: str, msg: AssessmentRequest):
    """
    Handles incoming assessment requests.
    Analyzes user answers and determines their level.
    """
    try:
        # Construct the prompt for Claude
        message = (
            f"Analyze this question and answer pair to determine the user's level "
            f"of understanding on a scale of 1-3 (1=beginner, 2=intermediate, 3=advanced). "
            f"Return only the number.\n\n"
            f"Question: {msg.question}\n"
            f"User's Answer: {msg.user_answer}"
        )

        # Get response from Claude
        response = anthropic.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}]
        )

        # Process the response
        level, feedback = analyze_response(response.content[0].text)
        
        # Log the assessment
        ctx.logger.info(f"Assessment completed - Level: {level}")
        ctx.logger.debug(f"Question: {msg.question}")
        ctx.logger.debug(f"Answer: {msg.user_answer}")
        ctx.logger.debug(f"Feedback: {feedback}")

        # Send response back to sender
        await ctx.send(sender, AssessmentResponse(level=level, feedback=feedback))

        # Update question generator if address is available
        if QUESTION_GENERATOR_ADDRESS:
            await ctx.send(QUESTION_GENERATOR_ADDRESS, LevelUpdate(level=level))
            ctx.logger.info(f"Sent level {level} to question generator")

    except Exception as e:
        error_msg = f"Error during assessment: {str(e)}"
        ctx.logger.error(error_msg)
        
        # Send error response back to sender
        await ctx.send(sender, AssessmentResponse(
            level=1,
            feedback="An error occurred during assessment. Defaulting to beginner level."
        ))
        
        # Notify question generator of error
        if QUESTION_GENERATOR_ADDRESS:
            await ctx.send(QUESTION_GENERATOR_ADDRESS, LevelUpdate(level=1))

@assessment_agent.on_event("startup")
async def initialize(ctx: Context):
    """
    Handles agent startup tasks.
    """
    ctx.logger.info(f"Assessment Agent is starting. Address: {ctx.address}")
    ctx.logger.info(f"Using Claude API endpoint")
    print(f"Assessment Agent Address: {ctx.address}")

@assessment_agent.on_event("shutdown")
async def cleanup(ctx: Context):
    """
    Handles agent shutdown tasks.
    """
    ctx.logger.info("Assessment Agent is shutting down")

if __name__ == "__main__":
    assessment_agent.run()