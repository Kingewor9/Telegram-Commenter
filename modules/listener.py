import random
from telethon import events
from modules.comment_generator import generate_comment
from modules.delay_manager import wait_random_delay

def register_handlers(client, cfg):
    print(f"Registering handler for channels: {cfg.CHANNELS}")

    @client.on(events.NewMessage(chats=cfg.CHANNELS))
    async def handler(event):
        chat = getattr(event.chat, 'username', None) or getattr(event.chat, 'id', None)
        print(f"Handler triggered for chat: {chat}")

        # Skip chance
        if random.random() < cfg.SKIP_PROBABILITY:
            print(f"Skipped commenting on {chat}")
            return

        await wait_random_delay(cfg.DELAY_RANGE)

        post_text = event.message.message or ""
        comment_text = generate_comment(post_text, cfg.MODE)

        # Demo: print instead of sending
        print(f"[{chat}] → would comment: {comment_text}")

        if not cfg.LOG_ONLY:
            try:
                # Reply to the message. For channel posts, replying to the post will typically
                # create a comment in the linked discussion (if available).
                print(f"Attempting to send comment to chat {chat}")
                await event.reply(comment_text)
                print("Comment sent")
            except Exception as e:
                print("Error sending comment:", e)
