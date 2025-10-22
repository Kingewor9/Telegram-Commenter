import random
import time
import asyncio
import re
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetFullChannelRequest
from modules.comment_generator import generate_comment
from modules.delay_manager import wait_random_delay
import config as cfg

# Simple in-memory queue for replies: list of dicts {linked, event_msg_id, channel_id, comment_text, enqueued_at}
reply_queue = []

def register_handlers(client, cfg):
    print(f"Registering handler for channels: {cfg.CHANNELS}")

    # Track last send timestamps per linked discussion (chat id) to avoid flood limits
    last_sent = {}
    # Track server-requested blocked-until timestamps per linked discussion
    next_allowed = {}

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
                                discussion_msg_id = getattr(discussion_msg, 'id', None)
                            except Exception as e:
                                # get_discussion_message may not exist or may fail; fall back to scanning the discussion
                                discussion_msg = None
                                discussion_msg_id = None
                                print('get_discussion_message not available or failed:', e)

                            if discussion_msg_id:
                                try:
                                    await client.send_message(linked, comment_text, reply_to=discussion_msg_id)
                                    print('Comment sent to linked discussion (as reply)')
                                except Exception as e:
                                    # Try to parse a server-requested wait from the RPC error string
                                    try:
                                        msg = str(e)
                                        m = re.search(r"wait of (\d+) seconds", msg)
                                        wait_seconds = int(m.group(1)) if m else None
                                    except Exception:
                                        wait_seconds = None

                                    if wait_seconds:
                                        next_allowed[linked] = time.time() + wait_seconds
                                        print('Server asked to wait', wait_seconds, 'seconds before sending to', linked)
                                    else:
                                        print('Error sending reply to linked discussion:', e)
                            else:
                                # Attempt to send a plain message immediately so users see something.
                                sent_id = None
                                try:
                                    m = await client.send_message(linked, comment_text)
                                    sent_id = getattr(m, 'id', None)
                                    print('Sent plain message to linked discussion (will convert later if possible)', sent_id)
                                except Exception as e:
                                    # parse server wait errors like: "A wait of 881 seconds is required before sending another message in this chat"
                                    wait_seconds = None
                                    try:
                                        msg = str(e)
                                        m = re.search(r"wait of (\d+) seconds", msg)
                                        if m:
                                            wait_seconds = int(m.group(1))
                                        else:
                                            # fallback to grabbing first number of seconds mentioned
                                            m2 = re.search(r"(\d+) seconds", msg)
                                            if m2:
                                                wait_seconds = int(m2.group(1))
                                    except Exception:
                                        wait_seconds = None

                                    if wait_seconds:
                                        next_allowed[linked] = time.time() + wait_seconds
                                        print('Error sending immediate plain message to linked discussion: server requires wait of', wait_seconds, 'seconds')
                                        # If the required wait is longer than REPLY_QUEUE_MAX_WAIT we usually
                                        # avoid enqueuing a job that will certainly timeout. Allow optional
                                        # long waits via config.
                                        if wait_seconds > cfg.REPLY_QUEUE_MAX_WAIT and not getattr(cfg, 'REPLY_QUEUE_ALLOW_LONG_WAIT', False):
                                            print('Required wait exceeds reply-queue max wait; not enqueuing job')
                                        else:
                                            give_up_at = time.time() + cfg.REPLY_QUEUE_MAX_WAIT
                                            if wait_seconds > cfg.REPLY_QUEUE_MAX_WAIT:
                                                # compute a give-up time based on server wait + optional slack
                                                slack = getattr(cfg, 'REPLY_QUEUE_LONG_WAIT_SLACK', 60)
                                                give_up_at = time.time() + wait_seconds + slack
                                            print('Enqueuing reply job to wait for discussion message to appear (give_up_at=', give_up_at, ')')
                                            reply_queue.append({
                                                'linked': linked,
                                                'channel_id': getattr(event.chat, 'id', None),
                                                'event_msg_id': getattr(event.message, 'id', None),
                                                'comment_text': comment_text,
                                                'sent_message_id': None,
                                                'enqueued_at': time.time(),
                                                'blocked_until': next_allowed.get(linked, None),
                                                'give_up_at': give_up_at,
                                            })
                                            print('Reply job enqueued (sent_message_id=', None, ')')
                                        # skip the normal enqueue below since we've already handled it
                                        return
                                    else:
                                        print('Error sending immediate plain message to linked discussion:', e)
                                # If we get here we either enqueued above or already printed the error
                                retries = 4
                                backoff = [2, 5, 10, 15]
                                search_limit = getattr(cfg, 'REPLY_QUEUE_SEARCH_LIMIT', 500)
                                for attempt in range(retries):
                                    try:
                                        # Increase search window
                                        recent = await client.get_messages(linked, limit=search_limit)
                                        for m in recent:
                                            # Direct check: some messages expose reply_to_msg_id directly
                                            rid_direct = getattr(m, 'reply_to_msg_id', None)
                                            if rid_direct and rid_direct == getattr(event.message, 'id', None):
                                                discussion_msg_id = m.id
                                                print('Found discussion message by direct reply_to_msg_id mapping')
                                                break

                                            # Check reply_to mapping (message in linked chat replying to the channel post)
                                            rt = getattr(m, 'reply_to', None)
                                            if rt:
                                                # reply_to may be an object with reply_to_msg_id
                                                rid = getattr(rt, 'reply_to_msg_id', None)
                                                if rid == getattr(event.message, 'id', None):
                                                    discussion_msg_id = m.id
                                                    print('Found discussion message by nested reply_to mapping')
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
                            cooldown = getattr(cfg, 'COOLDOWN', 300)  # default cooldown per linked discussion in seconds
                            last = last_sent.get(linked, 0)
                            # respect server-requested next_allowed as well
                            na = next_allowed.get(linked, 0)
                            wait_needed = max(0, cooldown - (now - last), na - now)
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
                                    # Respect the server ask and record next allowed time
                                    next_allowed[linked] = time.time() + fw.seconds
                                    await asyncio.sleep(fw.seconds)
                                    last_sent[linked] = time.time()
                                except Exception as e:
                                    # parse server-requested wait from generic RPC error
                                    try:
                                        msg = str(e)
                                        m = re.search(r"wait of (\d+) seconds", msg)
                                        wait_seconds = int(m.group(1)) if m else None
                                    except Exception:
                                        wait_seconds = None

                                    if wait_seconds:
                                        next_allowed[linked] = time.time() + wait_seconds
                                        print('Server asked to wait', wait_seconds, 'seconds before sending to', linked)
                                    else:
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


    # Background task to process queued reply jobs
    async def process_reply_queue():
        print('Reply queue processor started')
        while True:
            now = time.time()
            to_remove = []
            for i, job in enumerate(list(reply_queue)):
                # Use job-specific give_up_at if present otherwise fall back to global max wait
                give_up = job.get('give_up_at', job['enqueued_at'] + cfg.REPLY_QUEUE_MAX_WAIT)
                if now > give_up:
                    print('Dropping reply job due to timeout', job)
                    reply_queue.pop(i)
                    continue

                linked = job['linked']
                # try to find discussion message similar to above
                discussion_msg_id = None
                try:
                    search_limit = getattr(cfg, 'REPLY_QUEUE_SEARCH_LIMIT', 500)
                    recent = await client.get_messages(linked, limit=search_limit)
                    for m in recent:
                        # Direct reply_to_msg_id
                        rid_direct = getattr(m, 'reply_to_msg_id', None)
                        if rid_direct and rid_direct == job['event_msg_id']:
                            discussion_msg_id = m.id
                            print('Found discussion message by direct reply_to_msg_id mapping (queue)')
                            break

                        rt = getattr(m, 'reply_to', None)
                        if rt:
                            rid = getattr(rt, 'reply_to_msg_id', None)
                            if rid == job['event_msg_id']:
                                discussion_msg_id = m.id
                                print('Found discussion message by nested reply_to mapping (queue)')
                                break

                        ff = getattr(m, 'fwd_from', None)
                        if ff:
                            cid = getattr(ff, 'channel_id', None)
                            cpost = getattr(ff, 'channel_post', None)
                            if cid == job['channel_id'] and cpost == job['event_msg_id']:
                                discussion_msg_id = m.id
                                print('Found discussion message by fwd_from mapping (queue)')
                                break

                        # Entities and URL patterns
                        entities = getattr(m, 'entities', None)
                        if entities:
                            try:
                                for ent in entities:
                                    url = getattr(ent, 'url', None)
                                    if url:
                                        # direct id match in URL
                                        if str(job['event_msg_id']) in url:
                                            discussion_msg_id = m.id
                                            print('Found discussion message by entity URL mapping (queue)')
                                            break
                                        # check common t.me/c/<abs>/<post> and t.me/<username>/<post> patterns
                                        post_id = str(job['event_msg_id'])
                                        if re.search(rf"t\.me/c/\d+/{post_id}", url) or re.search(rf"t\.me/.+/{post_id}", url):
                                            discussion_msg_id = m.id
                                            print('Found discussion message by t.me URL pattern (queue)')
                                            break
                                if discussion_msg_id:
                                    break
                            except Exception:
                                pass
                    # also check the message text itself (some clients embed t.me links directly in text)
                    if not discussion_msg_id:
                        for m in recent:
                            text = getattr(m, 'message', '') or getattr(m, 'raw_text', '')
                            if text and str(job['event_msg_id']) in text:
                                discussion_msg_id = m.id
                                print('Found discussion message by text containing post id (queue)')
                                break
                except Exception as e:
                    print('Error scanning linked discussion in reply queue:', e)

                if discussion_msg_id:
                    # respect cooldown
                    try:
                        # If we previously sent a plain message, delete it first (if permitted)
                        sent_id = job.get('sent_message_id')
                        if sent_id:
                            try:
                                await client.delete_messages(linked, [sent_id])
                                print('Deleted previous plain message', sent_id)
                            except Exception as e:
                                print('Could not delete previous plain message', sent_id, e)

                        # respect server-requested next_allowed as well
                        na = next_allowed.get(linked, 0)
                        if time.time() < na:
                            print('Skipping queued send: server requested wait until', na)
                        else:
                            await client.send_message(linked, job['comment_text'], reply_to=discussion_msg_id)
                            print('Queued comment sent as reply to discussion message', discussion_msg_id)
                    except FloodWaitError as fw:
                        print('Reply queue FloodWaitError, sleeping', fw.seconds)
                        await asyncio.sleep(fw.seconds)
                        next_allowed[linked] = time.time() + fw.seconds
                    except Exception as e:
                        # parse server-requested wait from generic RPC error
                        try:
                            msg = str(e)
                            m = re.search(r"wait of (\d+) seconds", msg)
                            wait_seconds = int(m.group(1)) if m else None
                        except Exception:
                            wait_seconds = None

                        if wait_seconds:
                            next_allowed[linked] = time.time() + wait_seconds
                            print('Reply queue: server asked to wait', wait_seconds, 'seconds before sending to', linked)
                        else:
                            print('Error sending queued comment:', e)
                    finally:
                        # remove job
                        try:
                            reply_queue.remove(job)
                        except ValueError:
                            pass
                else:
                    # If mapping still not found and debug dumping is enabled, log a compact view
                    if getattr(cfg, 'DEBUG_DUMP_RECENT', False):
                        try:
                            dump_limit = min(10, getattr(cfg, 'REPLY_QUEUE_SEARCH_LIMIT', 50))
                            snapshot = await client.get_messages(linked, limit=dump_limit)
                            print('--- Debug dump: recent messages for linked', linked, '---')
                            for m in snapshot:
                                rid = getattr(m, 'reply_to_msg_id', None)
                                rt = getattr(m, 'reply_to', None)
                                ff = getattr(m, 'fwd_from', None)
                                entities = getattr(m, 'entities', None)
                                snippet = (getattr(m, 'message', '') or '')[:80].replace('\n', ' ')
                                print({'id': getattr(m, 'id', None), 'snippet': snippet, 'reply_to_msg_id': rid, 'nested_reply': getattr(rt, 'reply_to_msg_id', None) if rt else None, 'fwd_from': {'channel_id': getattr(ff, 'channel_id', None) if ff else None, 'channel_post': getattr(ff, 'channel_post', None) if ff else None}, 'has_entities': bool(entities)})
                            print('--- end debug dump ---')
                        except Exception as e:
                            print('Could not produce debug dump for linked', linked, e)

            await asyncio.sleep(cfg.REPLY_QUEUE_POLL_INTERVAL)

    # start the background reply queue processor
    try:
        # schedule in client's loop
        client.loop.create_task(process_reply_queue())
    except Exception:
        # If client.loop doesn't exist yet, start a background asyncio task via asyncio
        try:
            asyncio.get_event_loop().create_task(process_reply_queue())
        except Exception:
            pass
