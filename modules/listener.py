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

                            # If we couldn't find it that way, search recent messages in the linked chat
                            if not discussion_msg_id:
                                try:
                                    recent = await client.get_messages(linked, limit=200)
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
                                except Exception as e:
                                    print('Error searching linked discussion messages:', e)

                            # If we found the discussion message, reply to it specifically
                            if discussion_msg_id:
                                try:
                                    await client.send_message(linked, comment_text, reply_to=discussion_msg_id)
                                    print('Comment sent to linked discussion (as reply)')
                                except Exception as e:
                                    print('Error sending reply to linked discussion:', e)
                            else:
                                print('No specific discussion message found; sending a plain message to linked discussion')
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
