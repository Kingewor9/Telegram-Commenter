import random
from telethon import events
from telethon.tl.functions.channels import GetFullChannelRequest
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
                # If the message comes from a broadcast channel, sending a normal reply
                # to the channel is often not allowed (you need admin privileges). Instead
                # check whether the channel has a linked discussion (a group) and send
                # the comment there. Otherwise, fall back to replying and log errors.
                if getattr(event.chat, 'broadcast', False):
                    try:
                        full = await client(GetFullChannelRequest(event.chat))
                        linked = getattr(full.full_chat, 'linked_chat_id', None)
                    except Exception as e:
                        print('Could not fetch full channel info:', e)
                        linked = None

                    if linked:
                        print(f"Sending comment to linked discussion {linked}")
                        await client.send_message(linked, comment_text)
                        print('Comment sent to linked discussion')
                    else:
                        print('No linked discussion found; attempting to reply (may require admin)')
                        await event.reply(comment_text)
                        print('Reply sent (if permitted)')
                else:
                    # Not a broadcast channel — safe to reply normally
                    await event.reply(comment_text)
                    print('Reply sent')
            except Exception as e:
                print('Error sending comment:', e)
