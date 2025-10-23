import random

COMMENTS = [
    "Test your football IQ on my profile today",
    "Visit my profile now to take the official Football IQ test and see your score.",
    "See if you have the knowledge of a coach by taking the Football IQ quiz on my profile.",
    "This is your chance to prove you know the game—the Football IQ test is available on my profile.",
    "Visit my profile today for instant access to the Football IQ challenge."
]

def generate_comment(post_text: str, mode="RANDOM"):
    if mode == "RANDOM":
        return random.choice(COMMENTS)

    # placeholder for AI mode
    return f"(AI simulated comment related to: {post_text[:50]}...)"
