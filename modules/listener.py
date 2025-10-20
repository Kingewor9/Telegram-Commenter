import random
from telethon import events
from modules.comment_generator import generate_comment
from modules.delay_manager import wait_random_delay

def register_handlers(client, cfg):
    @client.on(events.NewMessage(chats=cfg.CHANNELS))
    async def handler(event):
        # Skip chance
        if random.random() < cfg.SKIP_PROBABILITY:
            print(f"Skipped commenting on {event.chat.username}")
            return

        await wait_random_delay(cfg.DELAY_RANGE)

        post_text = event.message.message or ""
        comment_text = generate_comment(post_text, cfg.MODE)

        # Demo: print instead of sending
        print(f"[{event.chat.username}] → would comment: {comment_text}")

        if not cfg.LOG_ONLY:
            discussion = await event.get_discussion_message()
            if discussion:
                await client.send_message(discussion.chat_id, comment_text)
