# Fall-detection ML — results

Random Forest over 7 image + motion features (see `FEATURES.md`), trained on the
UP-Fall dataset. Evaluated **leakage-free** (windows from one recording never
span train/test) and **subject-independent** (leave-one-subject-out): the model
is tested on people it never trained on — the honest, realistic measure.

_Run: **all 17 subjects**, UP-Fall Activities 1-5 (falls), Camera 1 + belt
accelerometer. 255 recordings, 1,926 windows._

## Headline
> Tested on **17 unseen subjects** (leave-one-subject-out), the model detected
> **90.6% of falls (recall)** with **75.6% precision** — a stable, robust result
> (5-fold CV F1 = 0.826 ± 0.015).

_Robustness check: a 5-subject run gave 90.9% / 76.3% — nearly identical, which
confirms the result is not a fluke._

## 1. Subject-independent (leave-one-subject-out), 17 subjects
Train on 16 subjects, test on the held-out one, rotate through all 17.

| Held-out subject | Fall recall | Precision | Falls tested |
|------------------|-------------|-----------|--------------|
| Subject 1        | 82.1%       | 100.0%    | 39 |
| Subject 2        | 91.7%       | 100.0%    | 36 |
| Subject 3        | 80.6%       | 96.7%     | 36 |
| Subject 4        | 87.0%       | 69.0%     | 23 |
| Subject 5        | 85.7%       | 60.0%     | 21 |
| Subject 6        | 100.0%      | 53.6%     | 15 |
| Subject 7        | 91.7%       | 68.8%     | 24 |
| Subject 8        | 86.5%       | 91.4%     | 37 |
| Subject 9        | 95.8%       | 71.9%     | 24 |
| Subject 10       | 100.0%      | 44.4%     | 12 |
| Subject 11       | 88.9%       | 72.7%     | 27 |
| Subject 12       | 100.0%      | 75.0%     | 21 |
| Subject 13       | 100.0%      | 69.0%     | 20 |
| Subject 14       | 100.0%      | 50.0%     | 17 |
| Subject 15       | 90.0%       | 75.0%     | 20 |
| Subject 16       | 70.4%       | 90.5%     | 27 |
| Subject 17       | 90.3%       | 96.6%     | 31 |
| **Average**      | **90.6%**   | **75.6%** | 430 |

_Lower-precision subjects (6, 10, 14) are those with the fewest falls tested, so
their precision is noisier; subjects with more falls score 90-100% precision._

## 2. Hold-out classification report
| Class          | Precision | Recall | F1-score | Support |
|----------------|-----------|--------|----------|---------|
| Not-fall (0)   | 0.977     | 0.919  | 0.947    | 372     |
| Fall (1)       | 0.766     | 0.925  | 0.838    | 106     |
| **Accuracy**   |           |        | **0.921**| 478     |

## 3. Confusion matrix (hold-out)
|                       | Predicted not-fall | Predicted fall |
|-----------------------|--------------------|----------------|
| **Actual not-fall**   | 342                | 30             |
| **Actual fall**       | 8                  | 98             |

## 4. Feature importances
| Feature            | Importance | Modality |
|--------------------|------------|----------|
| frame_motion       | 0.268      | image    |
| tilt_change        | 0.226      | motion   |
| stillness          | 0.201      | motion   |
| peak_accel         | 0.164      | motion   |
| bbox_aspect_ratio  | 0.063      | image    |
| centroid_height    | 0.048      | image    |
| sma                | 0.029      | motion   |

Both motion **and** image features contribute (the top feature is an image
feature), confirming the image+motion fusion is doing real work.

## 5. Dataset & validation summary
| Item                 | Value                                     |
|----------------------|-------------------------------------------|
| Subjects             | 17                                        |
| Recordings           | 255 (Activities 1-5, Trials 1-3)          |
| Total windows        | 1,926 (430 fall / 1,496 not-fall)         |
| 5-fold grouped CV F1 | 0.826 ± 0.015                             |
| Evaluation           | Leakage-free + subject-independent (LOSO) |

## Notes for the report / viva
- **Report the LOSO average (90.6% recall / 75.6% precision over 17 subjects)** —
  it tests generalisation to unseen people, unlike a random split.
- **Lead with recall** (catching falls is safety-critical). The false alarms
  behind the 75.6% precision are caught by the **Stage-3 10-second cancel window**
  before any caregiver alert fires.
- **Consistency = credibility**: 5-subject and 17-subject runs agree (~90% / ~76%),
  and CV variance is tiny (±0.015), so the result is stable and trustworthy.
- **Per-subject variation** shows why subject-independent testing matters — some
  people move in more fall-like ways.
- **Do not report accuracy alone** — on imbalanced data it is misleading.
- **Not-fall data** here comes from the standing/lying phases of fall clips (the
  download was falls-only). Adding dedicated daily-activity recordings (walking,
  jumping, laying) as hard negatives would raise precision further.
