# TEAM 0.5: parameters

Table of contents:

[**STEM Optimal Lens Settings	1**](#stem-optimal-lens-settings)

[**STEM beam current settings	2**](#stem-beam-current-settings)

[Picoammeter measurements	2](#picoammeter-measurements)

[**STEM Scanning and Collection Parameters	2**](#stem-scanning-and-collection-parameters)

[STEM imaging dwell time optimization and flyback time	2](#stem-imaging-dwell-time-optimization-and-flyback-time)

[HAADF-STEM collection semi-angles	2](#haadf-stem-collection-semi-angles)

[300 kV	2](#300-kv)

[200kV	3](#200kv)

[80 kV	5](#80-kv)

[**TEM	6**](#tem)

[Oneview Nyquist frequencies	6](#oneview-nyquist-frequencies)

[300 kV	6](#300-kv-1)

[80 kV	7](#80-kv-1)

[**4D Camera	7**](#4d-camera)

[Camera length calibrations	7](#camera-length-calibrations)

[300 kV	7](#300-kv-2)

[80 kV (in progress)	8](#80-kv-\(in-progress\))

[**STEM Objective Lens registry values (UltraTwin only)	8**](#stem-objective-lens-registry-values-\(ultratwin-only\))

# STEM Optimal Lens Settings {#stem-optimal-lens-settings}

These are all for spot size 7

| Voltage (kV) | Date | C1 (%) | C2 (%) | C3 (%) | MC (%) | Obj (%) | Diff(%) |
| ----- | :---: | :---- | :---- | :---- | :---- | :---- | :---- |
| 50 | 2020/09/11 | 42.179 | 20.687 | 33.676 | 72.323 | 67.4717 | 48.255 |
| 80 | 2018/07/26 | 43.148 | 20.258 | 33.492 | 55.554 | 71.861 | 60.104 |
| 200 | 2020/09/14 | 42.951 | 19.737 | 35.488 | \-30.766 | 89.2575 | 12.445 |
| 300 | 2018/07/26 | 42.951 | 10.661 | 37.023 | \-86.372 | 93.5684 | 22.010 |

# STEM beam current settings {#stem-beam-current-settings}

## Picoammeter measurements {#picoammeter-measurements}

Andreas Schmid attached a Keithley Picoammeter to the TEAM Stage chopsticks. We then could measure the current with the beam hitting the chopsticks. This is a way to approximate the actual beam current. See [TEAM 0.5: beam current measurements](https://docs.google.com/spreadsheets/d/1Dv1SLPyumw0NLXOfnJ-hcglPyY-2d9NcEvScn4sGS8U/edit#gid=0) for conversion between screen current, OneView counts, and picoammeter.

# STEM Scanning and Collection Parameters {#stem-scanning-and-collection-parameters}

## STEM imaging dwell time optimization and flyback time {#stem-imaging-dwell-time-optimization-and-flyback-time}

Flyback time is 3.6 ms and trigger is 16.6 ms (60 Hz):  
(dpL+f)n/60  
(dpL+.0036)60n  
*d* is dwell time,pL is the number of pixels in a line (1024, 512, etc.),  *f* is the flyback time, and *n* is an integer. Good numbers: 1k: 13 µs or  29 µs; 2k: 14 µs or 30  µs

| Dwell time (µs) | Frame time, 1kx1k (s) |
| :---: | :---: |
| \< 13.2 | 17 (max) |
| 13 – 29.1 | 35 |
| 29.2 – 45 | 52 |
| \> 46 | 69 |

## HAADF-STEM collection semi-angles {#haadf-stem-collection-semi-angles}

Note: outer angle is limited by image corrector transfer lenses. So, outer values may not be reliable. It is possible to turn off the image corrector to improve outer angle and reduce distortions.

### 300 kV {#300-kv}

See data in .../service/20210628 \- 300 kV camera lengths

| 300 kV Camera Length  | Inner semi-angle (mrad) | Outer semi-angle \= 5\*inner (mrad) |
| :---: | :---: | :---: |
| 530 mm | 12 | 58 |
| 420 | 15 | 73 |
| 330 | 18 | 92 |
| 256 | 22 | 115 |
| 215 | 28 | 141 |
| 170 | 35 | 177 |
| 135 | 44 | 222 |
| 105 | 56 | 282 |
| 85 | 72 | 358 |
| 68 | 90 | 448 |
| 54 | 111 | 553 |
| 43 | 136 | 681 |
| 34 | 168 | 844 |

![][image1]

### 200kV {#200kv}

See service/20210708 \- 200 kV camera lengths  
See service/20211018 \- 200 kV camera lengths (correct 265mmCL)

| 200 kV Camera Length | Inner semi-angle (mrad) | Outer semi-angle (mrad) |
| ----- | ----- | ----- |
| 670 | 11 | 53 |
| 530 | 13 | 67 |
| 420 | 17 | 85 |
| 330 | 21 | 107 |
| 265 | 26 | 132 |
| 215 | 59 | 169 |
| 170 | 42 | 209 |
| 135 | 58 | 265 |
| 105 | 67 | 336 |
| 85 | 85 | 425 |
| 68 | 106 | 530 |
| 54 | 132 | 659 |
| 43 | 1609 | 799 |
| 34 | 202 | 1007 |

![][image2]

### 80 kV {#80-kv}

See service/20210928 \- 80 kV camera lengths

| 80 kV Camera Length | Inner semi-angle (mrad) | Outer semi-angle (mrad) |
| ----- | ----- | ----- |
| 530 | 15 | 73 |
| 420 | 18 | 92 |
| 330 | 23 | 117 |
| 265 | 29 | 144 |
| 215 | 37 | 187 |
| 170 | 46 | 231 |
| 135 | 58 | 292 |
| 105 | 74 | 372 |
| 85 | 93 | 464 |
| 68 | 115 | 575 |
| 54 | 144 | 720 |
| 43 | 178 | 891 |
| 34 | 223 | 1115 |
| 8 | 955 | 4775 |

![][image3]

# TEM {#tem}

## Oneview Nyquist frequencies {#oneview-nyquist-frequencies}

### 300 kV {#300-kv-1}

| Magnification | Nyquist frequency (1/nm) |
| :---- | :---- |
| SA 100 kx | 0.87 |
| SA 130 kx | 1.13 |
| SA 160 kx | 1.40 |
| SA 205 kx | 1.78 |
| SA 260 kx | 2.33 |
| SA 330 kx | 2.93 |

### 80 kV  {#80-kv-1}

| Magnification | Nyquist frequency (1/nm) |
| :---- | :---- |
| SA 78k | 1.01 |
| SA 100k | 1.3 |
| SA 130k | 1.7 |
| SA 160k | 2.1 |
| SA 205k | 2.7 |
| SA 260k | 3.4 |
| SA 330k | 4.5 |
| Mh 145 kx | 1.7 |
| Mh 180 kx | 2.37 |
| Mh 230 kx | 4.6 |

# 4D Camera {#4d-camera}

## Camera length calibrations {#camera-length-calibrations}

### 300 kV {#300-kv-2}

| Indicated camera length (mm) | Camera constant (A mm) | Calculated camera length (mm) | Calibrated pixel size (Å\-1) | Method |
| :---- | :---- | :---- | :---- | :---- |
| 34 |  | 47 |  | Convergence angle |
| 43 |  | 60 |  | Convergence angle |
| 54 |  | 74 |  | Convergence angle |
| 68 |  | 92 |  | approximate |
| 85 | 2.19 | 111 |  | Au |
| 105 | 2.82 | 143 | 0.00353 | Au |
| 135 |  | 180 | 0.00282 | MoO3 (?) |
| 330 |  | 446 | 0.00224 | MoO3 (?) |
| 420 |  | 548 | 0.00093 | MoO3 (?) |

### 80 kV (in progress) {#80-kv-(in-progress)}

| Indicated camera length (mm) | Calculated camera length (mm) |
| :---- | :---- |
|  |  |
|  |  |

* STEM rotation vs. diffraction pattern offset  
  * These values can be used in the DPC Jupyter notebook template from Distiller. Other software might have a different convention.  
  * In each case the TIA and Gatan stem rotation values are set to zero  
  * TIA and Gatan have the same rotation sense. So, you can add the two values together and then add this offset

| Voltage (kV) | Angle (degrees) | DPC notebook flip needed? |
| :---- | :---- | :---- |
| 80 | \-160 | True |
| 200 | \-9 | True |
| 300 | \-9 | True |
