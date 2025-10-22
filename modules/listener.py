import random
import time
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetFullChannelRequest
from modules.comment_generator import generate_comment
from modules.delay_manager import wait_random_delay

def register_handlers(client, cfg):
    print(f"Registering handler for channels: {cfg.CHANNELS}")

    # Track last send timestamps per linked discussion (chat id) to avoid flood limits
    last_sent = {}

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
                            # First try the convenient helper if available
                            discussion_msg_id = None
                            try:
                                # Some Telethon versions provide get_discussion_message on the event
                                discussion_msg = await event.get_discussion_message()
                                if discussion_msg:
                                    discussion_msg_id = discussion_msg.id
                                    print('Found discussion message via event.get_discussion_message()')
                            except Exception as e:
                                print('event.get_discussion_message not available or failed:', e)

                            # If we couldn't find it that way, search recent messages in the linked chat.
                            # Retry a few times with backoff because the discussion message can be created slightly
                            # after the channel post.
                            if not discussion_msg_id:
                                retries = 4
                                backoff = [2, 5, 10, 15]
                                for attempt in range(retries):
                                    try:
                                        # Increase search window
                                        recent = await client.get_messages(linked, limit=500)
                                        for m in recent:
                                            # Check reply_to mapping (message in linked chat replying to the channel post)
                                            rt = getattr(m, 'reply_to', None)
                                            if rt:
                                                # reply_to may be an object with reply_to_msg_id
                                                rid = getattr(rt, 'reply_to_msg_id', None)
                                                if rid == getattr(event.message, 'id', None):
                                                    discussion_msg_id = m.id
                                                    print('Found discussion message by reply_to mapping')
                                                    break

                                            # Check forwarded-from mapping (some clients forward link)
                                            ff = getattr(m, 'fwd_from', None)
                                            if ff:
                                                cid = getattr(ff, 'channel_id', None)
                                                cpost = getattr(ff, 'channel_post', None)
                                                if cid == getattr(event.chat, 'id', None) and cpost == getattr(event.message, 'id', None):
                                                    discussion_msg_id = m.id
                                                    print('Found discussion message by fwd_from mapping')
                                                    break
                                            # Check entities for a link back to the original post (some discussion messages
                                            # include a t.me link to the post). Match by message id presence in any URL.
                                            entities = getattr(m, 'entities', None)
                                            if entities:
                                                try:
                                                    for ent in entities:
                                                        url = getattr(ent, 'url', None)
                                                        if url and str(getattr(event.message, 'id', '')) in url:
                                                            discussion_msg_id = m.id
                                                            print('Found discussion message by entity URL mapping')
                                                            break
                                                    if discussion_msg_id:
                                                        break
                                                except Exception:
                                                    pass
                                        if discussion_msg_id:
                                            break
                                    except Exception as e:
                                        print('Error searching linked discussion messages (attempt', attempt+1, '):', e)

                                    # if not found, wait before next attempt
                                    if attempt < len(backoff):
                                        await asyncio.sleep(backoff[attempt])

                            # Now attempt to send while respecting local cooldowns and Telegram flood-wait
                            now = time.time()
                            cooldown = 300  # default cooldown per linked discussion in seconds
                            last = last_sent.get(linked, 0)
                            wait_needed = max(0, cooldown - (now - last))
                            if wait_needed > 0:
                                print(f"Local cooldown: need to wait {int(wait_needed)}s before sending to {linked}")
                            else:
                                try:
                                    if discussion_msg_id:
                                        await client.send_message(linked, comment_text, reply_to=discussion_msg_id)
                                        print('Comment sent to linked discussion (as reply)')
                                    else:
                                        print('No specific discussion message found; sending a plain message to linked discussion')
                                        await client.send_message(linked, comment_text)
                                        print('Comment sent to linked discussion')

                                    # record timestamp
                                    last_sent[linked] = time.time()
                                except FloodWaitError as fw:
                                    # Telethon tells us how many seconds to wait
                                    print('FloodWaitError: need to wait', fw.seconds, 'seconds')
                                    # Respect the server ask
                                    await asyncio.sleep(fw.seconds)
                                    last_sent[linked] = time.time()
                                except Exception as e:
                                    print('Error sending comment:', e)
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
