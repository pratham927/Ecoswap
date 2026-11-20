# EcoSwap taste pilot: protocol, not results

Status: not conducted. This document does not establish taste preservation.

## Small proposed study

Choose three dishes that your group can cook consistently, for example beef/turkey filling, a butter/margarine baked item, and a cream/milk sauce. Adapt choices to your group's food preferences. Decide the exact substitution, fraction, quantities and preparation before collecting ratings. The demo scenarios are ingredient-list models; develop and record workable cooking instructions first.

Recruit 6–10 consenting volunteers for a small descriptive pilot. Disclose ingredients and check dietary restrictions before serving. Participation is optional. Record participant codes, not names. This is not a powered equivalence study.

1. Prepare original and adapted versions under comparable conditions; record actual ingredient masses, serving temperature and any adjustment to seasoning or cooking time.
2. Have a helper assign A/B labels, with the original assigned to A for half the participants and to B for the remainder. Keep a codebook separate from the rating sheet. Also counterbalance which sample is tasted first.
3. Serve equal portions. Do not tell participants which sample has the lower modelled footprint.
4. Ask for **flavour similarity**, 1 = very different and 7 = very similar. Ask separately for **liking of A** and **liking of B**, 1 = dislike strongly and 7 = like strongly. Invite comments about texture, aroma and aftertaste.
5. Enter `original_code` from the codebook only after collecting responses. Complete the supplied CSV. Do not fill blank responses with guessed values.
6. Run `python scripts/analyze_taste_pilot.py results/taste_ratings_template.csv`.

Report the number of participants and responses, per-dish means, individual ratings, and adapted-minus-original liking. Similarity and liking answer different questions: people can prefer a dish that tastes different. A small pilot cannot justify a universal claim of unchanged taste. Recalculate emissions with actual masses and mapped states for the dishes prepared.
