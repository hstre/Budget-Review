"""Experiment: is the extraction prompt, not the model, what fails on legal prose?

Segmenting the document did not restore recall, which ruled out context length.
What is left is that the extractor is asked the wrong question for this kind of
text. Two parts of the production prompt were written for project proposals:

  1. The claim-type vocabulary. Seven of its twenty-one values — target,
     capacity, resource, baseline, forecast, delivery, budget — describe a plan,
     not an argument. A model that must label every claim from a list that does
     not fit its document has a reason to propose fewer of them.
  2. "Decompose polished prose aggressively: an elegant sentence may contain
     several claims." That describes marketing writing. A court decision argues
     in long clause-heavy steps that nobody would call elegant, so the
     instruction may simply not apply itself.

The gold spans are whole argument passages of about 300 characters, while this
contract asks for atomic propositions. Reaching 80 per cent overlap therefore
needs a passage decomposed exhaustively, not summarised into its main assertion
— which is exactly what the second instruction is supposed to produce.

To keep the comparison to one variable, this does not rewrite the prompt. It
takes the production prompt and replaces those two passages, asserting first
that each is present, so a prompt that has since changed fails the run instead
of quietly testing nothing.

The same harness answers a second question. The output budget of 16,384 tokens
is self-imposed: the model accepts up to 384,000. Raising it is therefore
possible, and --max-tokens measures what that buys — whether a document past
the truncation point completes, and what the resulting graph is worth. A larger
budget that turns a loud failure into a quiet, thin dossier would be a loss for
this tool, so the number to watch is recall, not whether the run finishes.

Usage:
    prompt_variant_extract.py <document> <document-id> <output-packet.json>
                              [--prompt production|neutral] [--max-tokens N]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from budget_review.gate import sha256_text  # noqa: E402
from budget_review.models import SchemaError, SemanticPacket  # noqa: E402
from budget_review.prompts import extraction_prompt  # noqa: E402
from budget_review.provider import (  # noqa: E402
    DeepSeekProvider,
    ModelConfig,
    _reject_invalid_proposals,
)

ORIGINAL_DECOMPOSE = (
    "Decompose polished prose aggressively: an elegant sentence may contain several claims."
)
NEUTRAL_DECOMPOSE = (
    "Decompose the text exhaustively. A sentence with several clauses normally carries "
    "several claims, and a passage that argues in steps carries one claim per step. Never "
    "summarise a passage into its main assertion: every distinct assertion in it is its own "
    "claim, including the ones that only restate a rule, record what is undisputed, or draw "
    "the conclusion."
)

ORIGINAL_TYPES_LEAD = "Allowed claim_type values:"
TYPES_NOTE = (
    "\nMany of these values describe plans and will not occur in other kinds of text. Never "
    "let a poorly fitting label stop you from proposing a claim: use the closest value, or "
    "'other'."
)


EDITS = ("decompose", "vocabulary")


def variant_prompt(
    document_id: str, document: str, edits: tuple[str, ...] = EDITS
) -> tuple[str, str]:
    """The production prompt with the named edits applied and nothing else.

    Both together raised recall on one court decision from 16 of 24 to 20. That
    told us the bundle works, not which half does, and the two edits address
    different things: one asks for exhaustive decomposition in place of a
    sentence about elegant prose, the other says a poorly fitting label is never
    a reason to drop a claim. Applying them singly is what separates them.
    """
    system, user = extraction_prompt(document_id, document, "general")
    if system.count(ORIGINAL_DECOMPOSE) != 1:
        raise SystemExit("production prompt no longer contains the decomposition sentence")
    if system.count(ORIGINAL_TYPES_LEAD) != 1:
        raise SystemExit("production prompt no longer contains the claim-type list")

    if "decompose" in edits:
        system = system.replace(ORIGINAL_DECOMPOSE, NEUTRAL_DECOMPOSE)
    if "vocabulary" in edits:
        line_end = system.index("\n", system.index(ORIGINAL_TYPES_LEAD))
        system = system[:line_end] + TYPES_NOTE + system[line_end:]
    return system, user


def extract_packet(document_id: str, system: str, user: str, max_tokens: int) -> dict:
    """One extraction, with the production path's single schema repair round.

    Without that round the experiment is more brittle than the path it is
    compared against, and a rejected label would read as a worse result rather
    than as one extra call. Legal prose reaches for labels the proposal-shaped
    vocabulary does not have — "conclusion" among them.
    """
    provider = DeepSeekProvider()
    validation_error: SchemaError | None = None
    for attempt in range(2):
        active_system = system
        if validation_error is not None:
            active_system += (
                "\n\nYour previous JSON was rejected by the local closed-schema gate: "
                f"{validation_error}. Regenerate the complete JSON object. Correct the "
                "schema violation; do not add new fields. Omit any uncertain relation."
            )
        response, metadata = provider.complete_json(
            system=active_system,
            user=user,
            config=ModelConfig(model_id="deepseek-v4-flash", thinking=False),
            max_tokens=max_tokens,
        )
        candidate = {
            "schema_version": "content-review.semantic-packet/0.2",
            "document_id": document_id,
            "provenance": {
                "provider": "deepseek",
                "model_id": str(metadata["model"]),
                "run_id": str(uuid.uuid4()),
                "prompt_hash": sha256_text(active_system + "\n" + user),
                "output_hash": str(metadata["output_hash"]),
                "temperature": 0.0,
            },
            "claims": response.get("claims"),
            "relations": response.get("relations", []),
        }
        try:
            # The same closed schema the production path uses, so a packet this
            # experiment writes cannot be looser than a real one.
            SemanticPacket.from_dict(candidate)
        except SchemaError as exc:
            validation_error = exc
            print(f"  Schema-Ablehnung in Versuch {attempt + 1}: {exc}", file=sys.stderr)
            if attempt == 0:
                continue
            # And not stricter than a real one either. Production drops the
            # single malformed proposal and keeps the packet; an experiment that
            # dies here instead would score the prompt on a document the product
            # handles, which is how the sweep lost 001-77936 over one unknown
            # relation_type.
            recovered = _reject_invalid_proposals(candidate)
            if recovered is not None:
                print(
                    f"  {len(recovered.claim_rejections)} Claims, "
                    f"{len(recovered.relation_rejections)} Relationen abgelehnt, "
                    "Paket behalten",
                    file=sys.stderr,
                )
                return recovered.to_dict()
            continue
        return candidate
    raise SystemExit(f"packet failed the closed schema twice: {validation_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("document_id")
    parser.add_argument("out_path", type=Path)
    parser.add_argument(
        "--prompt",
        choices=("production", "neutral", "decompose", "vocabulary"),
        default="neutral",
        help="neutral applies both edits; decompose and vocabulary apply one each",
    )
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args()

    document = args.document.read_text(encoding="utf-8")
    document_id = args.document_id
    out_path = args.out_path

    if args.prompt == "production":
        system, user = extraction_prompt(document_id, document, "general")
    else:
        edits = EDITS if args.prompt == "neutral" else (args.prompt,)
        system, user = variant_prompt(document_id, document, edits)
    print(
        f"Prompt: {args.prompt}, max_tokens {args.max_tokens}, "
        f"{len(system)} Zeichen System, {len(user)} Zeichen User"
    )

    packet_data = extract_packet(document_id, system, user, args.max_tokens)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet_data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"{len(packet_data['claims'])} Claims, "
        f"{len(packet_data['relations'])} Relationen -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
