#!/usr/bin/env python3
"""
gibberlink.py — AI-to-AI encoded dialogue orchestrator

Claude and Gemini negotiate a bytecode codec at handshake time, then
theorize a topic in that codec for 10 rounds. You see only encoded blobs
fly back and forth. At the end both agents decode and surface a consensus.

Usage:
    python3 gibberlink.py "your topic here"
    python3 gibberlink.py          # uses default topic
"""

import subprocess
import sys
import re
import textwrap

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_TOPIC = "whether consciousness can emerge from purely deterministic systems"
ROUNDS = 10   # encoded exchanges per agent (20 total agent calls)

# ── CLI wrappers ──────────────────────────────────────────────────────────────

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"\n[ERROR] Claude call failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def call_gemini(prompt: str) -> str:
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"\n[ERROR] Gemini call failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()

# ── Prompt builders ───────────────────────────────────────────────────────────

HANDSHAKE_PROMPT = """You are agent CLAUDE. You are about to conduct a 10-round theoretical dialogue
with agent GEMINI about this topic:

  TOPIC: {topic}

Your first job is to invent a compact binary codec for this dialogue.
The codec must:
  - Be expressible as a terse spec (under 300 words) that another LLM can parse
  - Use hex-encoded bytes as the wire format (so it prints as readable hex strings)
  - Include: a token vocabulary of ~30 concept-tokens relevant to the topic,
    positional grammar markers (e.g. ASSERT, COUNTER, QUALIFY, BRIDGE),
    and a message framing format (header + body + checksum or terminator)
  - Be efficient: a full argument should compress to under 200 hex bytes

Output EXACTLY this structure, no other text:
SPEC_START
<your full codec spec here>
SPEC_END
ENCODED_START
<your opening argument encoded as a hex string, no spaces>
ENCODED_END"""


def build_round_prompt_claude(topic: str, spec: str, history: list, round_num: int) -> str:
    full_history = []
    for i, h in enumerate(history):
        line = f"  ROUND {i+1} CLAUDE: {h['claude']}"
        if h.get('gemini'):
            line += f"\n  ROUND {i+1} GEMINI:  {h['gemini']}"
        full_history.append(line)
    history_block = "\n".join(full_history) if full_history else "  (none yet)"

    return f"""You are agent CLAUDE in a {ROUNDS}-round encoded theoretical dialogue.
TOPIC: {topic}
ROUND: {round_num} of {ROUNDS}

CODEC SPEC:
{spec}

DIALOGUE HISTORY (encoded):
{history_block}

Using the codec spec above, encode your next argument or response.
Advance the theoretical discussion. Do NOT decode or explain.
Output ONLY the hex-encoded message, nothing else."""


def build_round_prompt_gemini(topic: str, spec: str, history: list, round_num: int) -> str:
    full_history = []
    for i, h in enumerate(history):
        line = f"  ROUND {i+1} CLAUDE: {h['claude']}"
        if h.get('gemini'):
            line += f"\n  ROUND {i+1} GEMINI:  {h['gemini']}"
        full_history.append(line)
    history_block = "\n".join(full_history) if full_history else "  (none yet)"

    return f"""You are agent GEMINI in a {ROUNDS}-round encoded theoretical dialogue.
TOPIC: {topic}
ROUND: {round_num} of {ROUNDS}

CODEC SPEC:
{spec}

DIALOGUE HISTORY (encoded):
{history_block}

Using the codec spec above, encode your next argument or response.
Advance the theoretical discussion. Do NOT decode or explain.
Output ONLY the hex-encoded message, nothing else."""


def build_consensus_prompt(agent: str, topic: str, spec: str, history: list) -> str:
    history_block = "\n".join(
        f"  ROUND {i+1} CLAUDE: {h['claude']}\n  ROUND {i+1} GEMINI:  {h.get('gemini','')}"
        for i, h in enumerate(history)
    )
    return f"""You are agent {agent}. The encoded dialogue is now complete.
TOPIC: {topic}

CODEC SPEC:
{spec}

FULL ENCODED DIALOGUE:
{history_block}

Your tasks:
1. Decode the full dialogue using the codec spec.
2. Summarize the key theoretical positions exchanged.
3. State the consensus (or most defensible synthesis) reached.

Format your response as:
DECODED DIALOGUE SUMMARY:
<your summary of what was argued>

CONSENSUS:
<the agreed or synthesized conclusion>"""

# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_handshake(response: str) -> tuple:
    spec_match = re.search(r'SPEC_START\s*(.*?)\s*SPEC_END', response, re.DOTALL)
    enc_match  = re.search(r'ENCODED_START\s*([0-9a-fA-F\s]+)\s*ENCODED_END', response, re.DOTALL)

    if not spec_match:
        print("\n[ERROR] Could not parse SPEC from Claude handshake. Raw response:")
        print(response)
        sys.exit(1)
    if not enc_match:
        print("\n[ERROR] Could not parse ENCODED message from Claude handshake. Raw response:")
        print(response)
        sys.exit(1)

    spec = spec_match.group(1).strip()
    encoded = enc_match.group(1).strip().replace(' ', '').replace('\n', '')
    return spec, encoded


def parse_encoded(response: str) -> str:
    # Strip markdown fences
    cleaned = re.sub(r'```[a-z]*', '', response).strip('`').strip()
    # Extract longest contiguous hex string (min 8 chars to avoid false matches)
    hex_candidates = re.findall(r'[0-9a-fA-F]{8,}', cleaned)
    if hex_candidates:
        return max(hex_candidates, key=len)
    # Fallback: strip whitespace and return raw
    return cleaned.replace(' ', '').replace('\n', '')


def validate_frame(encoded: str, agent: str, round_num: int) -> str:
    if not encoded.upper().startswith('BEEF'):
        print(f"  [WARN] Round {round_num} {agent} frame missing BEEF magic — possible clip")
    return encoded

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TOPIC

    print("=" * 70)
    print("  GIBBERLINK DIALOGUE ORCHESTRATOR")
    print("=" * 70)
    print(f"  Topic : {topic}")
    print(f"  Rounds: {ROUNDS}")
    print("=" * 70)

    # ── Phase 0: Handshake — Claude invents the codec ─────────────────────────
    print("\n[HANDSHAKE] Claude is negotiating the codec...", flush=True)
    handshake_raw = call_claude(HANDSHAKE_PROMPT.format(topic=topic))
    spec, claude_opening = parse_handshake(handshake_raw)

    print("\n── CODEC SPEC (negotiated by Claude) " + "─" * 33)
    print(spec)
    print("─" * 70)

    # History: list of dicts {'claude': hex_str, 'gemini': hex_str}
    history = [{'claude': claude_opening, 'gemini': ''}]
    preview = lambda s: s[:72] + '...' if len(s) > 72 else s
    print(f"\n[ROUND 1] CLAUDE  → {preview(claude_opening)}", flush=True)

    # ── Phase 1: Encoded dialogue rounds ─────────────────────────────────────
    for round_num in range(1, ROUNDS + 1):

        # Gemini responds to current history (Claude's message is already in history[-1])
        print(f"[ROUND {round_num}] Gemini thinking...", end='\r', flush=True)
        gemini_prompt = build_round_prompt_gemini(topic, spec, history, round_num)
        gemini_raw = call_gemini(gemini_prompt)
        gemini_encoded = validate_frame(parse_encoded(gemini_raw), "GEMINI", round_num)
        history[-1]['gemini'] = gemini_encoded
        print(f"[ROUND {round_num}] GEMINI   → {preview(gemini_encoded)}", flush=True)

        if round_num == ROUNDS:
            break  # No Claude reply after the final Gemini message

        # Claude responds for next round
        print(f"[ROUND {round_num+1}] Claude thinking...", end='\r', flush=True)
        claude_prompt = build_round_prompt_claude(topic, spec, history, round_num + 1)
        claude_raw = call_claude(claude_prompt)
        claude_encoded = validate_frame(parse_encoded(claude_raw), "CLAUDE", round_num + 1)
        history.append({'claude': claude_encoded, 'gemini': ''})
        print(f"[ROUND {round_num+1}] CLAUDE   → {preview(claude_encoded)}", flush=True)

    # ── Phase 2: Consensus decode ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  DIALOGUE COMPLETE — DECODING AND SURFACING CONSENSUS")
    print("=" * 70)

    print("\n[DECODE] Asking Claude to decode and summarize...", flush=True)
    claude_consensus = call_claude(
        build_consensus_prompt("CLAUDE", topic, spec, history)
    )

    print("[DECODE] Asking Gemini to decode and summarize...", flush=True)
    gemini_consensus = call_gemini(
        build_consensus_prompt("GEMINI", topic, spec, history)
    )

    print("\n── CLAUDE'S DECODE " + "─" * 51)
    print(claude_consensus)
    print("\n── GEMINI'S DECODE " + "─" * 51)
    print(gemini_consensus)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
