"""Module for handling image-based prompts using GPT-4 Vision."""

import logging
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
import re
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

async def analyze_image(image_url: str) -> str | None:
    """Analyze an image using GPT-4 Vision.
    
    Args:
        image_url: URL of the image to analyze
        
    Returns:
        Analysis of the image if successful, None if analysis fails
    """
    logger.info(f"Analyzing image: {image_url}")
    
    try:
        # Initialize the model
        model = ChatOpenAI(model="gpt-4o-mini")
        
        # Create the message with image
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": "Please extract and provide the content from the image as it appears, whether it is text, symbols, or any other information. Focus solely on delivering the content without additional context or interpretation. Write this as if you are providing alt text for an image that a visually impaired person would use to gain the same understanding a sighted person would have by looking at the image, without additional verbal fluff. If there are image contains one or more graphs, charts, or tables, please attempt to provide the main conclusions drawn from the data presented. Please provide output in a similar form one would use in a detailed alt text"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            ]
        )
        
        # Try up to 2 times (initial attempt + 1 retry)
        for attempt in range(2):
            try:
                # Get the response
                response = await model.ainvoke([message])
                content = response.content
                
                # Check for the "unable to process" message
                if (content.lower().startswith("i'm unable") 
                    or content.lower().startswith("i am unable") 
                    or content.lower().startswith("i am sorry")
                    or content.lower().startswith("i apologize")
                    or content.lower().startswith("i'm sorry")):
                    if attempt == 0:
                        logger.warning(f"Got 'unable to process' message, retrying...")
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        logger.warning(f"Still unable to process after retry")
                        return None
                logger.info(f"Image analysis successful: {content}")
                return content
                
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"First attempt failed: {str(e)}, retrying...")
                    await asyncio.sleep(1)  # Brief pause before retry
                    continue
                raise  # Re-raise if second attempt fails
        
    except Exception as e:
        logger.error(f"Error analyzing image: {str(e)}")
        return None
