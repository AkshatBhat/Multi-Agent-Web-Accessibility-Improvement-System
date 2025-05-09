from autogen.agentchat import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
import json
import pickle
import os

# A silent proxy for driving “human” turns
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=1,
    code_execution_config={"use_docker": False}
)

# Load your UI JSON once
with open("test_data/test_file.json", "r", encoding="utf-8") as f:
    ui_json = json.load(f)

# 1) Make sure your JSON is a string
if isinstance(ui_json, dict):
    ui_str = json.dumps(ui_json)
else:
    ui_str = ui_json

# 2) Wrap your T5 agents exactly as before
class ChatWrapperAgent(AssistantAgent):
    def __init__(self, name: str, t5_agent):
        super().__init__(name=name)
        self.t5_agent = t5_agent

    def generate_reply(self, messages, sender=None, **kwargs):
        # take the content of the *first* message as raw JSON
        raw_json = messages[0]["content"]
        return self.t5_agent.handle(raw_json)

# Load magents from Pickle files
semantic_model = pickle.load(open("agent_pickles/semantic_agent.pkl", "rb"))
contrast_model = pickle.load(open("agent_pickles/contrast_agent.pkl", "rb"))
axe_agent = pickle.load(open("agent_pickles/axe_agent.pkl", "rb"))
image_caption_model = pickle.load(open("agent_pickles/image_captioning_agent.pkl", "rb"))

semantic_wrapper = ChatWrapperAgent("semantic-agent", semantic_model)
contrast_wrapper = ChatWrapperAgent("contrast-agent", contrast_model)
axe_wrapper = ChatWrapperAgent("axe-violations-agent", axe_agent)
image_captioning_wrapper = ChatWrapperAgent("image-captioning-agent", image_caption_model)

# 3) Manually invoke them on the same single‐element history:
history = [{"role": "user", "content": ui_str}]

semantic_summary  = semantic_wrapper.generate_reply(history)
contrast_summary = contrast_wrapper.generate_reply(history)
axe_violations_summary = axe_wrapper.generate_reply(history)
image_captioning_summary = image_captioning_wrapper.generate_reply(history)

combined_summary = (
    f"SemanticAgent: {semantic_summary}\n\n"
    f"ContrastAgent: {contrast_summary}\n\n"
    f"AxeViolationsAgent: {axe_violations_summary}\n\n"
    f"ImageCaptioningAgent: {image_captioning_summary}\n\n"
)

from autogen.agentchat import UserProxyAgent, GroupChat, GroupChatManager

# 1) Rebuild the echo agents around your summaries
class EchoAgent(AssistantAgent):
    def __init__(self, name: str, summary: str):
        super().__init__(name=name)
        self.summary = summary

    def generate_reply(self, messages=None, sender=None, **kwargs):
        return self.summary

echo_semantic = EchoAgent("semantic-agent", semantic_summary)
echo_contrast = EchoAgent("contrast-agent", contrast_summary)
echo_axe_violations = EchoAgent("axe-violations-agent", axe_violations_summary)
echo_image_captioning = EchoAgent("image-captioning-agent", image_captioning_summary)

# 2) Configure your proxy
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=1,
    code_execution_config={"use_docker": False}
)

# 3) Build the GroupChat with explicit round‑robin ordering

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

group_chat = GroupChat(
    agents=[
        user_proxy,
        echo_semantic,
        echo_contrast,
        echo_axe_violations,
        echo_image_captioning,
        visually_impaired_agent,
        motor_impaired_agent,
        color_blind_agent,
        fixing_agent
    ],
    messages=[],  # no pre‑seed
    max_round=9,
    speaker_selection_method="round_robin",
    allow_repeat_speaker=False
)

# 4) Bind a new manager
manager = GroupChatManager(
    groupchat=group_chat,
    llm_config={"model": "gpt-4", "temperature": 0}
)

# 5) Kick off with your combined summary; max_turns = 6 agents after the proxy
chat_result = user_proxy.initiate_chat(
    manager,
    message=combined_summary,
    clear_history=True,
    max_turns=1
)