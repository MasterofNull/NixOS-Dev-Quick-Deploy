---
doc_type: reference
title: Beginner operator guide — your AI system's human controls
status: draft
owner: hyperd
date: 2026-08-16
---

# Your AI system, in plain language

Status: draft
Owner: hyperd
Last Updated: 2026-08-16

> **Draft skeleton (look-ahead).** Drafted by the local lane + orchestrator-normalized while the
> Approval screen (ACP-P2) is in build. Finalize the screenshots + exact button labels when the
> surfaces ship. No technical knowledge is assumed anywhere in this guide — that is the whole point.

You operate your system through **three screens**, none of which require you to type commands:

| Screen | What it's for |
|---|---|
| **Dashboard** | Watch health at a glance — green means healthy, red means attention. |
| **Terminal Monitor** | The live log — watch work happen; look for "Done". |
| **Approval screen** | Approve plain-language decisions with a tap of your security key. |

---

## Getting Started

Welcome! Your local AI is like a helpful assistant living in your home office. You don't need to code;
you just check in using these simple screens.

**1. The Dashboard (health check).** Like a car's dashboard: green lights mean "All Systems Healthy."
If you see red, something needs attention. A quick glance tells you if your AI is ready to work.

**2. The Terminal Monitor (live log).** A window into your assistant's work — plain text scrolls by as
it works. Lines of activity are normal; watch for the final "Done" to know a task finished.

**3. The Approval screen (security key).** When the AI needs your go-ahead, it pauses and asks. A simple
screen shows a clear question like *"Activate the scheduler service?"* Tap your security key to say yes,
or Deny to say no. You are always in control.

**A simple daily habit:** in the morning, check the Dashboard for green lights; in the evening, clear any
pending items on the Approval screen. That's it.

---

## Using the Approval screen

When you see an approval card, take a moment to read it. Each card is written in plain language so you
can decide confidently without any technical expertise.

**What to look for:**
- **The request** — *what* action is being asked for (e.g., "Turn on the approval service").
- **The reason** — *why* it's needed right now.
- **The impact** — what happens if you approve, and whether it can be undone.

**How to decide:** you never need to understand any technical detail or code to choose. If the request
matches what you expect and the reason makes sense, tap **Approve** — your security key or fingerprint
will confirm it's really you. If anything looks wrong, unexpected, or you simply aren't sure, tap
**Deny** — denying is always safe, and nothing happens without your tap.

---

## Setting up your security key

Think of your security key as a house key for your AI system — either a small physical device you keep
safe, or your fingerprint. It's what proves an approval is really coming from *you*, so no software (not
even the AI itself) can approve things on your behalf. You never type a password.

Getting started is simple:
1. Open the setup screen and choose "Add security key."
2. Follow the prompt to plug in your device or scan your fingerprint.
3. Give it a name (like "Home key") so you recognize it.

**Do this next — register a second, backup key right away.** Keys get lost and devices break. A spare
means you never get locked out of your own system. It takes two minutes now and saves a lot of stress
later.

## Approving without a browser

Sometimes you can't use the web screen — during system recovery, or if the interface is down. Then you
use a plain command-line tool called `aq-approve`. It lists the same pending requests in the same plain
language, and you decide the same way.

It looks different, but it is **exactly as safe** as the normal screen: you still physically touch your
security key to confirm, which proves you're present and authorizing it yourself — no remote software can
do it for you. As always, check that what's shown matches what you expected before you touch your key; if
anything looks off, don't approve it.

## If you lose your security key

Take a breath — your system is safe, and this is manageable.

**If you registered a backup key:** just use that one. Nothing is lost — the system accepts either key.
This is exactly why the backup matters.

**If you lost *all* your keys:** you'll re-set-up access by **physically sitting at the computer itself**.
That can feel inconvenient, but it's deliberate — it means only someone with hands-on possession of your
machine can restore access, which keeps everyone else out. Recovery only re-registers a key; it never
approves anything by itself.

**Going forward:** keep a backup key somewhere safe and easy to find at home. That one habit prevents the
lock-out entirely.

## Handling common alerts

When you see a notification, don't panic. The screen uses color to tell you what's happening.

**Yellow warnings** are a gentle nudge — usually the system is thinking, loading, or waiting for a
process to finish. Most are purely informational; you likely just wait a moment. If a screen seems
stuck, refresh or reopen it.

**Red alerts** mean something needs attention now, such as a connection error. These are rare. If you
see red, stop — do **not** try to fix it by typing commands. Simply close and reopen the application
window; this resets the connection and often clears the issue. If it persists after a restart, take a
screenshot and ask for help. Never guess commands — just wait or restart.

---

## When to call for help

Knowing when to pause and ask is smart operating, not failure — it keeps small issues from becoming big
ones. Stop and contact your technical helper if you notice any of these:

- **A repeating red alert** that keeps coming back even after you close and reopen the app.
- **An approval request you don't understand** or that doesn't match anything you expected — Deny it and
  ask before approving.
- **Anything that looks like a security concern** — a request to change keys, access, or permissions
  that you didn't initiate.
- **The system stops responding** on all three screens and a restart doesn't bring it back.
- **Anything that just feels wrong** — trust that instinct and ask rather than approving.

Reaching out early is always the right call. Denying and asking never breaks anything; approving
something you don't understand might.

---

*Sources: this guide's prose was drafted on the local look-ahead lane (sections) and normalized by the
orchestrator (approval-screen completion; call-for-help reframed from generic hardware-safety to the
real software/operational situations). Finalize with real screenshots when ACP-P2 ships.*
