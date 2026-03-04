# Ablation Study Results

*Generated: 2026-03-04 20:30*

| Method | Acc↑ | Halluc↓ | Fidelity↑ | Complete↑ | BLEU-1↑ | BLEU-2↑ | ROUGE-1↑ | ROUGE-L↑ |
|--------|------|---------|-----------|-----------|--------|--------|---------|----------|
| Zero-Shot (no context, no verification) | 0.00 | N/A | 0% | 0% | 0.174 | 0.058 | 0.277 | 0.195 |
| RAG-Only (semantic context, no verification) | 0.00 | N/A | 0% | 0% | 0.097 | 0.037 | 0.172 | 0.121 |
| LegacyLens (Full Pipeline, no repetition) | 1.00 | 0.46 | 50% | 97% | 0.128 | 0.047 | 0.215 | 0.132 |
| LegacyLens + Repetition (Simple) | 1.00 | 0.38 | 47% | 94% | 0.124 | 0.044 | 0.209 | 0.140 |
| LegacyLens + Repetition (Verbose) | 0.92 | 0.54 | 48% | 91% | 0.127 | 0.044 | 0.216 | 0.143 |
| LegacyLens + Repetition (x3) | 0.77 | 0.38 | 64% | 95% | 0.122 | 0.040 | 0.208 | 0.131 |

*Corpus: 13 functions (10 Spring PetClinic + 3 Apache Ant-style legacy) | References: hand-written gold-standard summaries*
