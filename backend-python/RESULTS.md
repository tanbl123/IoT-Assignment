# Fall-detection ML — results

Random Forest over 7 image + motion features (see `FEATURES.md`), trained on the
UP-Fall dataset. Evaluated **leakage-free** (windows from one recording never
span train/test) and **subject-independent** (leave-one-subject-out): the model
is tested on people it never trained on — the honest, realistic measure.

_Run: 5 subjects, Activities 1-5 (falls) + a few daily activities. Numbers will
change if you add more data; rebuild with `build_dataset_upfall.py` and re-run
`train_model.py`._

## Headline
> On subjects it never trained on, the model caught **90.9% of falls (recall)**
> with **76.3% precision**, averaged over 5 held-out subjects.

## 1. Subject-independent (leave-one-subject-out)
Train on 4 subjects, test on the held-out 5th, rotate through all.

| Held-out subject | Fall recall | Precision | Falls tested |
|------------------|-------------|-----------|--------------|
| Subject 1        | 84.6%       | 84.6%     | 39           |
| Subject 2        | 88.9%       | 94.1%     | 36           |
| Subject 3        | 94.4%       | 91.9%     | 36           |
| Subject 4        | 91.3%       | 55.3%     | 23           |
| Subject 5        | 95.2%       | 55.6%     | 21           |
| **Average**      | **90.9%**   | **76.3%** | 155          |

## 2. Hold-out classification report
| Class          | Precision | Recall | F1-score | Support |
|----------------|-----------|--------|----------|---------|
| Not-fall (0)   | 0.944     | 0.844  | 0.891    | 141     |
| Fall (1)       | 0.577     | 0.811  | 0.674    | 37      |
| **Accuracy**   |           |        | **0.837**| 178     |

## 3. Confusion matrix (hold-out)
|                       | Predicted not-fall | Predicted fall |
|-----------------------|--------------------|----------------|
| **Actual not-fall**   | 119                | 22             |
| **Actual fall**       | 7                  | 30             |

## 4. Feature importances
| Feature            | Importance | Modality |
|--------------------|------------|----------|
| tilt_change        | 0.240      | motion   |
| stillness          | 0.231      | motion   |
| frame_motion       | 0.214      | image    |
| peak_accel         | 0.186      | motion   |
| centroid_height    | 0.052      | image    |
| bbox_aspect_ratio  | 0.050      | image    |
| sma                | 0.027      | motion   |

Both motion **and** image features contribute, confirming the image+motion
fusion is doing real work (not motion-only).

## 5. Dataset & validation summary
| Item                 | Value                                   |
|----------------------|-----------------------------------------|
| Subjects             | 5                                       |
| Recordings           | 77                                      |
| Total windows        | 687 (155 fall / 532 not-fall)           |
| 5-fold grouped CV F1 | 0.832 ± 0.048                           |
| Evaluation           | Leakage-free + subject-independent (LOSO) |

## Notes for the report / viva
- **Report the LOSO average (90.9% recall / 76.3% precision)** — it tests
  generalisation to unseen people, unlike a random split.
- **Lead with recall** (catching falls is safety-critical). The false alarms
  behind the 76% precision are caught by the **Stage-3 10-second cancel window**
  before any caregiver alert fires.
- **Per-subject spread** (Subjects 4-5 have lower precision) shows why
  subject-independent testing matters — some people move in more fall-like ways.
- **Do not report accuracy alone** — on imbalanced data it is misleading.
