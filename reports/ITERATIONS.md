# Stage-2 iteration journal (development seasons only)

Every configuration tried is recorded here, including failures.

### it01_open_base — market `open`

Main-line log loss (non-push, calibrated): model 0.69073 vs market-only 0.69344 → gain +27.1×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 69.5%. Same-day error correlation: +0.0033.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 12192 | 0.518 | 0.531 | 0.523–0.540 |
| 55%-60% | 1020 | 0.563 | 0.571 | 0.540–0.601 |
| 60%-65% | 76 | 0.613 | 0.579 | 0.467–0.684 |
| 65%-70% | 1 | 0.695 | 0.000 | 0.000–0.793 |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 31.5% (CI 28.5%–34.6%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.602 | 0.558–0.644 | 11.557 | 0.774 | 0.788 | 1.652 | -0.003 | 0.020 |
| hit_rate | validation | 383 | 1.000 | 0.572 | 0.522–0.620 | 11.016 | 0.761 | 0.786 | 1.693 | -0.031 | 0.041 |
| value_4.5pct | discovery | 299 | 0.614 | 0.632 | 0.576–0.685 | 11.006 | 0.794 | 0.789 | 1.694 | 0.072 | 0.051 |
| value_4.5pct | validation | 293 | 0.765 | 0.587 | 0.530–0.642 | 10.642 | 0.765 | 0.787 | 1.722 | 0.010 | 0.061 |
| value_8pct | discovery | 61 | 0.125 | 0.689 | 0.564–0.791 | 10.254 | 0.820 | 0.793 | 1.654 | 0.135 | 0.036 |
| value_8pct | validation | 87 | 0.227 | 0.575 | 0.470–0.673 | 9.701 | 0.753 | 0.790 | 1.686 | -0.031 | 0.049 |

### it02_open_rich — market `open`

Main-line log loss (non-push, calibrated): model 0.68872 vs market-only 0.69344 → gain +47.2×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 70.8%. Same-day error correlation: +0.0039.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 11952 | 0.520 | 0.541 | 0.532–0.550 |
| 55%-60% | 1567 | 0.564 | 0.591 | 0.566–0.615 |
| 60%-65% | 58 | 0.611 | 0.707 | 0.580–0.808 |
| 65%-70% | 0 | — | — | —–— |
| 70%-100% | 1 | 0.708 | 0.000 | 0.000–0.793 |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.0% (CI 31.9%–38.3%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.661 | 0.618–0.702 | 11.251 | 0.811 | 0.785 | 1.677 | 0.107 | 0.029 |
| hit_rate | validation | 383 | 1.000 | 0.627 | 0.577–0.674 | 10.394 | 0.789 | 0.784 | 1.750 | 0.100 | 0.072 |
| value_4.5pct | discovery | 350 | 0.719 | 0.654 | 0.603–0.702 | 10.797 | 0.807 | 0.786 | 1.710 | 0.118 | 0.051 |
| value_4.5pct | validation | 347 | 0.906 | 0.634 | 0.582–0.683 | 10.191 | 0.793 | 0.784 | 1.765 | 0.121 | 0.081 |
| value_8pct | discovery | 76 | 0.156 | 0.632 | 0.519–0.731 | 10.046 | 0.796 | 0.788 | 1.660 | 0.045 | 0.027 |
| value_8pct | validation | 167 | 0.436 | 0.671 | 0.596–0.737 | 9.572 | 0.808 | 0.786 | 1.697 | 0.139 | 0.043 |

### it03_open_rich_var — market `open`

Main-line log loss (non-push, calibrated): model 0.68868 vs market-only 0.69344 → gain +47.6×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 69.5%. Same-day error correlation: +0.0041.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 12022 | 0.520 | 0.541 | 0.532–0.550 |
| 55%-60% | 1635 | 0.564 | 0.592 | 0.568–0.616 |
| 60%-65% | 63 | 0.611 | 0.698 | 0.576–0.798 |
| 65%-70% | 1 | 0.695 | 0.000 | 0.000–0.793 |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.0% (CI 31.9%–38.3%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.667 | 0.624–0.708 | 11.057 | 0.811 | 0.786 | 1.696 | 0.130 | 0.040 |
| hit_rate | validation | 383 | 1.000 | 0.624 | 0.575–0.671 | 10.280 | 0.790 | 0.785 | 1.769 | 0.105 | 0.083 |
| value_4.5pct | discovery | 389 | 0.799 | 0.650 | 0.602–0.696 | 10.756 | 0.798 | 0.786 | 1.719 | 0.119 | 0.056 |
| value_4.5pct | validation | 363 | 0.948 | 0.631 | 0.580–0.679 | 10.178 | 0.792 | 0.785 | 1.777 | 0.121 | 0.089 |
| value_8pct | discovery | 111 | 0.228 | 0.721 | 0.631–0.796 | 10.056 | 0.842 | 0.788 | 1.661 | 0.195 | 0.026 |
| value_8pct | validation | 205 | 0.535 | 0.644 | 0.576–0.706 | 9.646 | 0.795 | 0.786 | 1.699 | 0.093 | 0.043 |

### it04_open_rich_var_t — market `open`

Main-line log loss (non-push, calibrated): model 0.68868 vs market-only 0.69344 → gain +47.6×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 69.5%. Same-day error correlation: +0.0041.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 12022 | 0.520 | 0.541 | 0.532–0.550 |
| 55%-60% | 1635 | 0.564 | 0.592 | 0.568–0.616 |
| 60%-65% | 63 | 0.611 | 0.698 | 0.576–0.798 |
| 65%-70% | 1 | 0.695 | 0.000 | 0.000–0.793 |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.0% (CI 31.9%–38.3%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.667 | 0.624–0.708 | 11.057 | 0.811 | 0.786 | 1.696 | 0.130 | 0.040 |
| hit_rate | validation | 383 | 1.000 | 0.624 | 0.575–0.671 | 10.280 | 0.790 | 0.785 | 1.769 | 0.105 | 0.083 |
| value_4.5pct | discovery | 389 | 0.799 | 0.650 | 0.602–0.696 | 10.756 | 0.798 | 0.786 | 1.719 | 0.119 | 0.056 |
| value_4.5pct | validation | 363 | 0.948 | 0.631 | 0.580–0.679 | 10.178 | 0.792 | 0.785 | 1.777 | 0.121 | 0.089 |
| value_8pct | discovery | 111 | 0.228 | 0.721 | 0.631–0.796 | 10.056 | 0.842 | 0.788 | 1.661 | 0.195 | 0.026 |
| value_8pct | validation | 205 | 0.535 | 0.644 | 0.576–0.706 | 9.646 | 0.795 | 0.786 | 1.699 | 0.093 | 0.043 |

### it05_open_lgbm_var — market `open`

Main-line log loss (non-push, calibrated): model 0.68991 vs market-only 0.69344 → gain +35.3×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 59.9%. Same-day error correlation: +0.0051.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 12459 | 0.519 | 0.538 | 0.530–0.547 |
| 55%-60% | 722 | 0.559 | 0.602 | 0.566–0.638 |
| 60%-65% | 0 | — | — | —–— |
| 65%-70% | 0 | — | — | —–— |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 33.1% (CI 30.0%–36.3%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.630 | 0.587–0.672 | 11.805 | 0.800 | 0.786 | 1.640 | 0.035 | 0.005 |
| hit_rate | validation | 383 | 1.000 | 0.593 | 0.543–0.641 | 11.232 | 0.770 | 0.785 | 1.691 | 0.004 | 0.033 |
| value_4.5pct | discovery | 281 | 0.577 | 0.641 | 0.583–0.694 | 11.375 | 0.801 | 0.787 | 1.674 | 0.073 | 0.028 |
| value_4.5pct | validation | 312 | 0.815 | 0.599 | 0.544–0.652 | 11.024 | 0.771 | 0.785 | 1.708 | 0.025 | 0.045 |
| value_8pct | discovery | 9 | 0.018 | 0.889 | 0.565–0.980 | 10.194 | 0.944 | 0.788 | 1.630 | 0.451 | 0.009 |
| value_8pct | validation | 45 | 0.117 | 0.689 | 0.543–0.805 | 10.222 | 0.800 | 0.786 | 1.656 | 0.140 | 0.017 |

### it06_open_ens_var — market `open`

Main-line log loss (non-push, calibrated): model 0.68897 vs market-only 0.69344 → gain +44.8×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 61.9%. Same-day error correlation: +0.0042.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 12205 | 0.520 | 0.541 | 0.533–0.550 |
| 55%-60% | 1419 | 0.562 | 0.598 | 0.573–0.624 |
| 60%-65% | 17 | 0.609 | 0.941 | 0.730–0.990 |
| 65%-70% | 0 | — | — | —–— |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 34.8% (CI 31.7%–38.0%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.614 | 0.570–0.656 | 11.318 | 0.790 | 0.786 | 1.674 | 0.029 | 0.026 |
| hit_rate | validation | 383 | 1.000 | 0.619 | 0.569–0.666 | 10.629 | 0.785 | 0.785 | 1.739 | 0.076 | 0.063 |
| value_4.5pct | discovery | 351 | 0.721 | 0.621 | 0.569–0.670 | 10.974 | 0.791 | 0.786 | 1.703 | 0.059 | 0.046 |
| value_4.5pct | validation | 351 | 0.916 | 0.621 | 0.569–0.670 | 10.519 | 0.786 | 0.785 | 1.750 | 0.087 | 0.071 |
| value_8pct | discovery | 56 | 0.115 | 0.696 | 0.567–0.801 | 10.174 | 0.830 | 0.788 | 1.648 | 0.150 | 0.017 |
| value_8pct | validation | 146 | 0.381 | 0.610 | 0.529–0.685 | 9.836 | 0.774 | 0.785 | 1.680 | 0.025 | 0.031 |

### it07_close_rich_var — market `close`

Main-line log loss (non-push, calibrated): model 0.69248 vs market-only 0.69327 → gain +7.9×10⁻⁴ over 21287 games (2011-12..2017-18). Max two-sided P at the main line: 54.5%. Same-day error correlation: +0.0025.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 11501 | 0.507 | 0.530 | 0.520–0.539 |
| 55%-60% | 0 | — | — | —–— |
| 60%-65% | 0 | — | — | —–— |
| 65%-70% | 0 | — | — | —–— |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 877 cards, 2/2 = 29.0% (CI 26.1%–32.1%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 497 | 1.000 | 0.618 | 0.574–0.659 | 11.829 | 0.788 | 0.785 | 1.586 | -0.021 | -0.026 |
| hit_rate | validation | 383 | 1.000 | 0.606 | 0.556–0.653 | 11.629 | 0.770 | 0.783 | 1.616 | -0.022 | -0.014 |
| value_4.5pct | discovery | 48 | 0.097 | 0.521 | 0.383–0.655 | 10.896 | 0.719 | 0.785 | 1.648 | -0.142 | 0.014 |
| value_4.5pct | validation | 99 | 0.258 | 0.566 | 0.467–0.659 | 11.045 | 0.732 | 0.784 | 1.657 | -0.064 | 0.014 |
| value_8pct | discovery | 0 | 0.000 | — | None | — | — | — | — | — | — |
| value_8pct | validation | 0 | 0.000 | — | None | — | — | — | — | — | — |

### it08_2h_var — market `second_half`

Main-line log loss (non-push, calibrated): model 0.69282 vs market-only 0.69318 → gain +3.5×10⁻⁴ over 20586 games (2011-12..2017-18). Max two-sided P at the main line: 54.6%. Same-day error correlation: +0.0015.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 9520 | 0.508 | 0.512 | 0.502–0.522 |
| 55%-60% | 0 | — | — | —–— |
| 60%-65% | 0 | — | — | —–— |
| 65%-70% | 0 | — | — | —–— |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 877 cards, 2/2 = 26.1% (CI 23.3%–29.1%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 495 | 1.000 | 0.657 | 0.614–0.697 | 9.836 | 0.809 | 0.802 | 1.536 | 0.003 | -0.021 |
| hit_rate | validation | 383 | 1.000 | 0.587 | 0.538–0.636 | 8.851 | 0.774 | 0.787 | 1.643 | -0.036 | 0.014 |
| value_4.5pct | discovery | 131 | 0.265 | 0.649 | 0.564–0.725 | 8.559 | 0.790 | 0.795 | 1.626 | 0.056 | 0.029 |
| value_4.5pct | validation | 228 | 0.595 | 0.583 | 0.518–0.645 | 8.105 | 0.774 | 0.785 | 1.705 | -0.007 | 0.050 |
| value_8pct | discovery | 5 | 0.010 | 0.600 | 0.231–0.882 | 7.600 | 0.600 | 0.789 | 1.631 | -0.013 | 0.014 |
| value_8pct | validation | 50 | 0.131 | 0.540 | 0.404–0.670 | 7.380 | 0.740 | 0.786 | 1.669 | -0.098 | 0.031 |

### it09_open_rich_var_fix — market `open`

Main-line log loss (non-push, calibrated): model 0.68859 vs market-only 0.69344 → gain +48.5×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 69.5%. Same-day error correlation: +0.0042.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 11933 | 0.520 | 0.541 | 0.532–0.550 |
| 55%-60% | 1729 | 0.564 | 0.588 | 0.565–0.611 |
| 60%-65% | 71 | 0.612 | 0.676 | 0.561–0.773 |
| 65%-70% | 1 | 0.695 | 0.000 | 0.000–0.793 |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.1% (CI 32.0%–38.4%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.657 | 0.614–0.698 | 11.015 | 0.808 | 0.786 | 1.700 | 0.116 | 0.043 |
| hit_rate | validation | 383 | 1.000 | 0.595 | 0.545–0.643 | 10.330 | 0.770 | 0.785 | 1.769 | 0.056 | 0.083 |
| value_4.5pct | discovery | 395 | 0.811 | 0.646 | 0.597–0.691 | 10.711 | 0.799 | 0.786 | 1.724 | 0.114 | 0.059 |
| value_4.5pct | validation | 358 | 0.935 | 0.603 | 0.552–0.653 | 10.189 | 0.772 | 0.785 | 1.781 | 0.076 | 0.091 |
| value_8pct | discovery | 126 | 0.259 | 0.706 | 0.622–0.779 | 10.105 | 0.829 | 0.788 | 1.663 | 0.174 | 0.027 |
| value_8pct | validation | 203 | 0.530 | 0.631 | 0.562–0.694 | 9.626 | 0.786 | 0.786 | 1.703 | 0.073 | 0.046 |

### it10_open_style — market `open`

Main-line log loss (non-push, calibrated): model 0.68752 vs market-only 0.69344 → gain +59.3×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 70.1%. Same-day error correlation: +0.0035.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 10717 | 0.523 | 0.534 | 0.525–0.544 |
| 55%-60% | 3471 | 0.568 | 0.579 | 0.563–0.595 |
| 60%-65% | 359 | 0.614 | 0.666 | 0.615–0.713 |
| 65%-70% | 15 | 0.662 | 0.667 | 0.417–0.848 |
| 70%-100% | 1 | 0.701 | 0.000 | 0.000–0.793 |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.4% (CI 32.3%–38.6%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.616 | 0.572–0.658 | 10.372 | 0.784 | 0.787 | 1.778 | 0.097 | 0.093 |
| hit_rate | validation | 383 | 1.000 | 0.640 | 0.590–0.686 | 10.079 | 0.804 | 0.786 | 1.817 | 0.166 | 0.113 |
| value_4.5pct | discovery | 447 | 0.918 | 0.611 | 0.565–0.655 | 10.194 | 0.782 | 0.787 | 1.793 | 0.098 | 0.103 |
| value_4.5pct | validation | 360 | 0.940 | 0.636 | 0.585–0.684 | 9.928 | 0.801 | 0.786 | 1.831 | 0.169 | 0.122 |
| value_8pct | discovery | 283 | 0.581 | 0.629 | 0.571–0.683 | 9.654 | 0.788 | 0.788 | 1.713 | 0.080 | 0.057 |
| value_8pct | validation | 259 | 0.676 | 0.645 | 0.585–0.701 | 9.472 | 0.807 | 0.787 | 1.743 | 0.128 | 0.070 |

### it11_open_style_tt — market `open`

Main-line log loss (non-push, calibrated): model 0.68748 vs market-only 0.69344 → gain +59.6×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 70.1%. Same-day error correlation: +0.0036.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 10624 | 0.523 | 0.537 | 0.528–0.547 |
| 55%-60% | 3540 | 0.568 | 0.574 | 0.558–0.590 |
| 60%-65% | 363 | 0.614 | 0.664 | 0.614–0.711 |
| 65%-70% | 15 | 0.663 | 0.733 | 0.480–0.891 |
| 70%-100% | 1 | 0.701 | 0.000 | 0.000–0.793 |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 35.8% (CI 32.7%–39.1%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.622 | 0.578–0.664 | 10.323 | 0.786 | 0.787 | 1.781 | 0.108 | 0.094 |
| hit_rate | validation | 383 | 1.000 | 0.624 | 0.575–0.671 | 10.007 | 0.796 | 0.786 | 1.818 | 0.138 | 0.113 |
| value_4.5pct | discovery | 447 | 0.918 | 0.613 | 0.567–0.657 | 10.152 | 0.781 | 0.787 | 1.796 | 0.103 | 0.105 |
| value_4.5pct | validation | 357 | 0.932 | 0.619 | 0.568–0.668 | 9.858 | 0.793 | 0.786 | 1.833 | 0.140 | 0.123 |
| value_8pct | discovery | 294 | 0.604 | 0.629 | 0.573–0.682 | 9.662 | 0.787 | 0.788 | 1.713 | 0.079 | 0.056 |
| value_8pct | validation | 265 | 0.692 | 0.615 | 0.555–0.672 | 9.449 | 0.791 | 0.787 | 1.742 | 0.078 | 0.069 |

### it13_open_style_tt_int — market `open`

Main-line log loss (non-push, calibrated): model 0.68752 vs market-only 0.69344 → gain +59.2×10⁻⁴ over 16816 games (2011-12..2017-18). Max two-sided P at the main line: 68.1%. Same-day error correlation: +0.0039.

| bucket | n | pred | win | ci |
|---|---|---|---|---|
| 50%-55% | 10622 | 0.523 | 0.537 | 0.528–0.547 |
| 55%-60% | 3596 | 0.568 | 0.572 | 0.556–0.588 |
| 60%-65% | 364 | 0.614 | 0.657 | 0.606–0.704 |
| 65%-70% | 16 | 0.663 | 0.750 | 0.505–0.898 |
| 70%-100% | 0 | — | — | —–— |

Forced main-line pair (top-2 per slate): 868 cards, 2/2 = 34.8% (CI 31.7%–38.0%).

Buffered (alternate-line) cards:

| mode | period | cards | pct_slates | rate_2of2 | ci95 | avg_buffer_pts | leg_win | avg_leg_p | dbl_odds | roi_double | model_ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hit_rate | discovery | 487 | 1.000 | 0.622 | 0.578–0.664 | 10.270 | 0.789 | 0.787 | 1.784 | 0.112 | 0.097 |
| hit_rate | validation | 383 | 1.000 | 0.603 | 0.553–0.651 | 10.039 | 0.786 | 0.786 | 1.817 | 0.102 | 0.113 |
| value_4.5pct | discovery | 451 | 0.926 | 0.612 | 0.566–0.656 | 10.106 | 0.783 | 0.787 | 1.799 | 0.104 | 0.106 |
| value_4.5pct | validation | 356 | 0.930 | 0.601 | 0.549–0.651 | 9.883 | 0.784 | 0.786 | 1.833 | 0.108 | 0.123 |
| value_8pct | discovery | 298 | 0.612 | 0.631 | 0.575–0.684 | 9.624 | 0.790 | 0.788 | 1.715 | 0.084 | 0.058 |
| value_8pct | validation | 262 | 0.684 | 0.607 | 0.547–0.664 | 9.469 | 0.786 | 0.787 | 1.742 | 0.065 | 0.070 |


---
## Decisions between iterations (development seasons only)

* **Leak found and fixed (after it03):** `x_poss` was centred on the *season* median of
  pre-game tempo ratings, which uses later dates. Replaced by a trailing 30-day league
  mean. Validation buffered 2/2 for the it03 configuration fell from 62.4% to 59.5% —
  the honest number. All later iterations (it09+) use the fixed feature.
* **Rating hyper-parameters (discovery only, open market, log-loss gain ×10⁻⁴):**
  half-life 30d 57.7 · 45d 56.7 · 70d/prior 0.25 56.8 · ridge 8 54.1. Differences are
  within noise; the pre-existing default (45d, prior 0.15, ridge 3) is kept.
* **Model selection rule:** best development main-line log loss; ties within 1×10⁻⁴ →
  fewer features. it11 (+59.6) vs it10 (+59.3) is a tie → **it10_open_style** is chosen.
  (Card hit rates are deliberately NOT used to choose the model: they move ±3 points
  between near-identical models — sampling noise.)
* **Bug fixes in the card simulator:** masked buffers were multiplying (−1)×(−1) into
  "feasible" pairs; close-priced ROI required every game to have a close. Both fixed
  before the frontier below.
* **Card policy rule:** realism cap = alternate line at most 15 points from the market
  line; joint target J = smallest value on the grid {0.600, 0.625, 0.650, 0.700} whose
  pooled development 2/2 rate has a 95% Wilson lower bound ≥ 60%.
  J=0.600 → 62.5% (CI 59.3–65.7) ✗ ; **J=0.625 → 65.7% (CI 62.5–68.8) ✓**.
* **Robustness of the chosen policy (development):** every season 61.5–70.3%; legs
  independent within cards (outcome corr −0.004; product of leg rates 65.8% vs actual
  65.7%); both-Over 68.5%, both-Under 64.2%, mixed 62.5%; median buffer 10.5 pts.
* Configurations evaluated in stage 2 so far: 13 model iterations + 4 rating variants +
  24 card-policy cells. The holdout claim below is about ONE locked configuration.

---
## Stage 2 holdout (run once): 60.9% 2/2 on 363 cards (CI 55.8–65.8%). Edge decayed (log-loss gain 59→31).

## Engine v3 (developed after the stage-2 holdout, on 2007-21; untouched test = stage 2b)
| variant | train decay | calib decay | ll gain 2011-18 | ll gain 2018-21 | 2/2 2018-21 @J=.625 | @J=.65 |
|---|---|---|---|---|---|---|
| v2 (locked) | – | – | 59.0 | 31.4 | 61.2% | 64.5% |
| v3a | – | 0.7 | 59.2 | 27.9 | 60.1% | 64.2% |
| v3b | 0.8 | 0.7 | 57.1 | 34.1 | 62.5% | 65.3% |
| v3c | 0.8 | 0.5 | 56.7 | 32.8 | 63.4% | 65.6% |
| **v3d** | **0.6** | **0.6** | 53.3 | **37.3** | 62.8% | **66.0%** |

Rule: best recent-period (2018-21) log loss → v3d; J = smallest value whose 2018-21 Wilson
lower bound ≥ 60% → 0.65. Locked in config/stage3_v3_locked.yaml before stage 2b.

---
## NBA check (development seasons 2009-21, closing lines, score-only model + variance)
Main-line log-loss gain +8.8×10⁻⁴ (max two-sided P 58.6%). Buffered cards:

| J | max buffer | cards | 2/2 | 95% CI | avg buffer | fair double odds | ROI at 4.5% margin |
|---|---|---|---|---|---|---|---|
| 0.600 | 15 | 1683 | 60.7% | 58.4–63.0% | 12.7 | 1.54 | −6.3% |
| 0.625 | 15 | 1677 | 63.0% | 60.6–65.2% | 13.5 | 1.48 | −6.8% |
| 0.650 | 15 | 1511 | 65.7% | 63.3–68.1% | 14.3 | 1.43 | −6.3% |

Lesson: a 60%+ 2/2 rate can be *bought* in any market by moving lines ~13 points — but
without an information edge (NBA closing line) every such card loses roughly the margin.
The NCAAB opening line is where the edge that pays for the buffer exists.

---
## Stage 2b independent test (NCAAB 2021-22..2025-26, 6 US books, run once)
| engine | cards | 2/2 | 95% CI | line-shopping 2/2 | ROI open-priced 4.5% | ROI close-priced 4.5% |
|---|---|---|---|---|---|---|
| v2 (primary) | 664 | **63.9%** | 60.1–67.4% | 65.5% | +7.4% | −0.9% |
| v3 (secondary) | 664 | 64.5% | 60.7–68.0% | 66.9% | +3.6% | −3.1% |

Main-line singles at REAL opening prices (v2, P 55–60%): 3,526 bets, 56.9% win, ROI +8.5%
(median book) / +10.5% (best book). Full report: `stage2b_independent_test.md`.
