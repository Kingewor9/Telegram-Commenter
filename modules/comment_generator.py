import random

COMMENTS = [
    "🔥 Love this update!",
    "💪 Great insight.",
    "🚀 Keep the good work going!",
    "🙌 Awesome post!"
]

def generate_comment(post_text: str, mode="RANDOM"):
    if mode == "RANDOM":
        return random.choice(COMMENTS)

    # placeholder for AI mode
    return f"(AI simulated comment related to: {post_text[:50]}...)"
