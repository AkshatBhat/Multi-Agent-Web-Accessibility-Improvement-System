from agents.semantic_agent.agent import SemanticAgent
from agents.contrast_agent.agent import ContrastAgent
from agents.image_captioning_agent.agent import ImageCaptioningAgent
from agents.axe_violations_agent.agent import AxeViolationsAgent
from autogen import AssistantAgent

semantic_model = SemanticAgent(model_dir="trusha88/t5-semantic-agent")
contrast_model = ContrastAgent(model_dir="virajns2/contrast-violation-t5")
image_caption_model = ImageCaptioningAgent()
axe_agent = AxeViolationsAgent()

# Visually Impaired Agent
visually_impaired_agent = AssistantAgent(
    name="VisuallyImpairedAgent",
    system_message="You are a screen‑reader user. Given the following combined accessibility summary from the SemanticAgent and ContrastAgent, analyze it and respond with any additional issues or validations as you navigate the page. Include explicit references to each semantic and contrast finding.",
    llm_config={"model": "gpt-4", "temperature": 0}
)

# Motor-Impaired Agent
motor_impaired_agent = AssistantAgent(
    name="MotorImpairedAgent",
    system_message="You are a keyboard‑only user. Given the combined accessibility summary above, walk through the page structure and identify keyboard navigation barriers (e.g., tabindex issues, missing focus styles). Refer back to each semantic/contrast point in your response.",
    llm_config={"model": "gpt-4", "temperature": 0}
)

# Color-Blind Agent
color_blind_agent = AssistantAgent(
    name="ColorBlindAgent",
    system_message="You are a color‑blind user. Using the combined summary, assess whether the listed contrast ratios and semantic issues affect your ability to distinguish page elements. Call out any color‑related problems or confirm that the reported contrast ratio is sufficient.",
    llm_config={"model": "gpt-4", "temperature": 0}
)

# Fixing Agent
fixing_agent = AssistantAgent(
    name="FixingAgent",
    system_message="You are the final‑stage accessibility engineer. Given the full conversation history—including the semantic and contrast summaries and each simulation agent’s findings—produce a consolidated list of code‑level fixes. For each issue, reference which agent(s) raised it, then provide the minimal HTML/CSS/ARIA snippet needed to resolve it.",
    llm_config={"model": "gpt-4", "temperature": 0}
)