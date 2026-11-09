# Chứng minh 4 động cơ MD36L P27 (24 V) đủ lực cho robot Mecanum 9,7 kg

Tài liệu dựa trên mô hình Newton–Euler trong file *Động lực học robot mecanum* (slide 4–9).

---

## 0. Kết luận nhanh

| Nội dung | Kết quả |
|---|---|
| Khả năng tạo lực (Fx, Fy, Mz) | Bốn động cơ tạo được **mọi** tổ hợp, vì rank(B) = 3 |
| Mô-men lớn nhất trên một bánh (tình huống xấu nhất giả định) | 0,357 N·m, bằng **36%** mô-men định mức |
| Hệ số an toàn | **2,75** so với mô-men định mức, **17,6** so với mô-men stall |
| **Tốc độ tối đa lý thuyết (tịnh tiến thẳng hoặc ngang)** | **≈ 1,6 m/s** |
| Tốc độ tối đa thực tế (còn dư điện áp điều khiển) | **≈ 1,4 – 1,5 m/s** |
| Tốc độ liên tục an toàn (ở tốc độ định mức) | **≈ 1,36 m/s** |

---

## 1. Mô hình động lực học

Lực của động cơ dọc phương lăn bánh i (slide 4):

```
F_di = τ_i / r − F_ci          →   τ_i = r · (F_di + F_ci)
```

Tổng hợp lực lên thân (slide 6), với i = A, B, C, D:

```
Fx = F_dA + F_dB + F_dC + F_dD
Fy = F_dA − F_dB + F_dC − F_dD
Mz = (L+d) · ( −F_dA − F_dB + F_dC + F_dD )
```

Newton–Euler (slide 8, 9):

```
m·a_x = Fx        m·a_y = Fy        Iz·V̇z = Mz
a_x = V̇x − Vz·Vy       a_y = V̇y + Vz·Vx
```

Trong đó a_x, a_y là gia tốc thật của tâm, nên các số hạng Vz·V đã được tính sẵn.

---

## 2. Thông số động cơ

Nguồn: trang Wheeltec R5 (động cơ MD36L P27, DC chổi than, 24 V). Mã **E01122799 chưa được kiểm chứng riêng**; cần đối chiếu với nhãn động cơ thật.

| Thông số | Giá trị | Quy đổi |
|---|---|---|
| Điện áp | 24 V | |
| Công suất ghi nhãn | 60 W | công suất điện |
| Tốc độ không tải | 310 ± 12% vòng/phút | 32,5 rad/s |
| Tốc độ định mức | 260 ± 12% vòng/phút | 27,2 rad/s |
| Mô-men định mức | 10 kg·cm | **0,981 N·m** |
| Mô-men stall | ≥ 64 kg·cm | **6,28 N·m** |
| Dòng không tải / định mức / stall | ≤ 0,4 A / ≤ 2,9 A / ≤ 22,1 A | |
| Công suất cơ tại điểm định mức | 0,981 × 27,2 | **26,7 W** |

Kiểm tra nhất quán bằng đường đặc tính tuyến tính: tại 10 kg·cm, tốc độ là 310·(1 − 10/64) ≈ 262 vòng/phút, khớp với 260 vòng/phút.
Tính toán dùng công suất cơ 26,7 W (không dùng 60 W) để thiên về an toàn.

---

## 3. Giả thiết (cần thay bằng số thật của robot)

| Đại lượng | Giá trị giả định |
|---|---|
| Khối lượng m | 9,7 kg |
| Bán kính bánh r | 0,05 m (bánh Φ100 mm) |
| L + d | 0,30 m |
| Mô-men quán tính Iz | ≈ m(L² + d²) ≈ 0,44 kg·m² (cận trên) |
| Phản lực mỗi bánh N_i = mg/4 | 23,8 N |
| Hệ số cản lăn μ_r | 0,05 |
| Lực cản lăn mỗi bánh F_ci = μ_r·mg/4 | 1,19 N |
| Gia tốc yêu cầu | a_x = a_y = 1 m/s² |
| Gia tốc góc yêu cầu | V̇z = 3 rad/s² |

---

## 4. Bước 1: Lực cần có

```
Fx = m·a_x  = 9,7 × 1 = 9,7 N
Fy = m·a_y  = 9,7 × 1 = 9,7 N
Mz = Iz·V̇z  = 0,44 × 3 = 1,31 N·m
```

---

## 5. Bước 2: Bốn động cơ tạo được mọi (Fx, Fy, Mz)

Viết u = B·F với u = [Fx, Fy, Mz]ᵀ và F = [F_dA, F_dB, F_dC, F_dD]ᵀ:

```
        [   1       1       1       1    ]
B  =    [   1      −1       1      −1    ]
        [ −(L+d)  −(L+d)  +(L+d)  +(L+d) ]
```

Ba hàng của B đôi một vuông góc:

- hàng 1 · hàng 2 = 1 − 1 + 1 − 1 = 0
- hàng 1 · hàng 3 ∝ −1 − 1 + 1 + 1 = 0
- hàng 2 · hàng 3 ∝ −1 + 1 + 1 − 1 = 0

Cả ba hàng đều khác 0 nên **rank(B) = 3**, và B·Bᵀ = diag(4, 4, 4(L+d)²) khả nghịch.
Do đó với **bất kỳ** u luôn có nghiệm:

```
F = Bᵀ (B·Bᵀ)⁻¹ u

F_di = [ Fx + ε_i·Fy + s_i·Mz/(L+d) ] / 4
ε = (+1, −1, +1, −1)      s = (−1, −1, +1, +1)      (bánh A, B, C, D)
```

Ý nghĩa: robot đi được **theo cả ba bậc tự do** (tiến/lùi, ngang, xoay) và mọi tổ hợp của chúng.

Còn một hướng thừa N = (1, −1, −1, 1) vì B·N = 0: thêm hướng này thì lực lên thân không đổi. Khi điều khiển, cần đặt tốc độ bốn bánh theo động học đảo (mục 8) để các bánh không "đánh nhau" gây trượt.

---

## 6. Bước 3: Mỗi động cơ chịu được phần lực nào?

Lực dọc bánh tối đa của một động cơ:

```
F_max = τ_max / r − F_c
```

- Ở mô-men định mức (dùng liên tục): F_max = 0,981 / 0,05 − 1,19 = **18,4 N**
- Ở mô-men stall (chỉ tức thời): F_max ≈ **124 N**

Vì |F_di| ≤ ( |Fx| + |Fy| + |Mz|/(L+d) ) / 4, điều kiện đủ để cả bốn động cơ đáp ứng là:

```
|Fx| + |Fy| + |Mz|/(L+d)  ≤  4 · F_max
```

Với số liệu trên: **9,7 + 9,7 + 4,37 = 23,8 N ≤ 4 × 18,4 = 73,7 N** ✓ (chiếm 32%).

---

## 7. Bước 4: Kiểm tra bằng số, từng bánh

Với u = (9,7 N; 9,7 N; 1,31 N·m):

| Bánh | F_di (N) | τ = r(F_di + 1,19) (N·m) | % τ định mức |
|---|---|---|---|
| A | (9,7 + 9,7 − 4,37)/4 = 3,76 | 0,248 | 25% |
| B | (9,7 − 9,7 − 4,37)/4 = −1,09 | ≈ 0,005 | ≈ 0% |
| C | (9,7 + 9,7 + 4,37)/4 = 5,94 | **0,357** | **36%** |
| D | (9,7 − 9,7 + 4,37)/4 = 1,09 | 0,114 | 12% |

Kiểm tra ngược: ΣF_di = 9,70 N ✓; ΣεᵢF_di = 9,70 N ✓; (L+d)·ΣsᵢF_di = 1,31 N·m ✓.

Các trường hợp riêng (mỗi bánh):

| Trường hợp | τ cần (N·m) | % τ định mức |
|---|---|---|
| Chạy đều, chỉ thắng lực cản | 0,059 | 6% |
| Tịnh tiến a = 1 m/s² | 0,181 | 18% |
| Quay tại chỗ V̇z = 3 rad/s² | 0,114 | 12% |
| **Tổ hợp xấu nhất** | **0,357** | **36%** |

Độ nhạy: nếu μ_r = 0,1 (F_c = 2,38 N), mô-men xấu nhất tăng lên 0,416 N·m (42%), vẫn dư nhiều.

---

## 8. Tốc độ tối đa của xe

### 8.1. Động học đảo (suy ra từ bảo toàn công suất)

Từ ΣF_di·rω_i = Fx·Vx + Fy·Vy + Mz·Vz và mô hình lực ở mục 1:

```
r·ω_i = Vx + ε_i·Vy + s_i·(L+d)·Vz
```

Bốn tổ hợp dấu (ε, s) = (+,−), (−,−), (+,+), (−,+) đều xuất hiện, nên tốc độ bánh lớn nhất là:

```
max_i |r·ω_i| = |Vx| + |Vy| + (L+d)·|Vz|
```

Điều kiện chạy được (chính xác, không chỉ là điều kiện đủ):

```
|Vx| + |Vy| + (L+d)·|Vz|  ≤  r · ω_bánh,max
```

### 8.2. Tốc độ bánh tối đa

Khi chạy đều chỉ cần thắng lực cản: τ = r·F_c = 0,05 × 1,19 = 0,059 N·m.
Từ đường đặc tính tuyến tính ω = ω₀·(1 − τ/τ_stall):

```
ω = 32,46 × (1 − 0,0594 / 6,28) = 32,15 rad/s
v_max = r·ω = 0,05 × 32,15 ≈ 1,61 m/s
```

### 8.3. Tốc độ tối đa theo từng kiểu chuyển động

| Kiểu chuyển động | Công thức | Tốc độ tối đa lý thuyết (đủ 24 V) | Tại tốc độ định mức (260 vòng/phút) |
|---|---|---|---|
| Tiến/lùi (chỉ Vx) | \|Vx\| ≤ rω | **1,61 m/s** | 1,36 m/s |
| Đi ngang (chỉ Vy) | \|Vy\| ≤ rω | **1,61 m/s** | 1,36 m/s |
| Chéo 45° (Vx = Vy = V) | 2V ≤ rω | V = 0,80 m/s mỗi trục, hợp **1,14 m/s** | 0,96 m/s |
| Quay tại chỗ (chỉ Vz) | (L+d)·\|Vz\| ≤ rω | **5,35 rad/s** (≈ 306°/s) | 4,5 rad/s |
| Tổ hợp tổng quát | \|Vx\| + \|Vy\| + 0,3·\|Vz\| ≤ 1,61 | ví dụ Vx = 1,0; Vy = 0,3; Vz = 1,0 → 1,6 ✓ | |

### 8.4. Ảnh hưởng của dung sai và điện áp

Tốc độ không tải tỉ lệ thuận với điện áp, nên v_max ≈ 1,61 × (U / 24):

| Điều kiện | v_max thẳng |
|---|---|
| Nhà sản xuất, dung sai −12% | ≈ 1,43 m/s |
| Nhà sản xuất, dung sai +12% | ≈ 1,82 m/s |
| Pin sụt còn 22 V | ≈ 1,47 m/s |
| Pin sụt còn 21 V | ≈ 1,41 m/s |
| Còn dư 10% điện áp để bộ điều khiển PID bù tải | ≈ 1,45 m/s |

### 8.5. Khả năng tăng tốc khi đã chạy nhanh

Mô-men còn lại tại tốc độ ω: τ_avail = τ_stall·(1 − ω/ω₀), lực mỗi bánh F = τ_avail/r − F_c, gia tốc tối đa theo động cơ a = 4F/m.

| Tốc độ xe | τ_avail (N·m) | a tối đa theo động cơ |
|---|---|---|
| 1,36 m/s | ≈ 1,0 | ≈ 7,8 m/s² (bị giới hạn thực tế bởi độ bám bánh) |
| 1,50 m/s | ≈ 0,48 | ≈ 3,4 m/s² |

Đạt 1,5 m/s với a = 1 m/s² mất khoảng 1,5 s.

### 8.6. Kết luận về tốc độ

- **Tốc độ tối đa lý thuyết:** ≈ **1,6 m/s** khi tiến thẳng hoặc đi ngang.
- **Tốc độ tối đa thực tế nên dùng:** ≈ **1,4 – 1,5 m/s**.
- **Tốc độ liên tục an toàn (điểm định mức):** ≈ **1,36 m/s**.
- Khi đi chéo hoặc vừa đi vừa quay, tốc độ giảm theo công thức |Vx| + |Vy| + (L+d)|Vz| ≤ 1,6 m/s.

---

## 9. Kiểm tra công suất và dòng điện

| Hạng mục | Kết quả | So với giới hạn |
|---|---|---|
| Công suất khi tăng tốc a = 1 m/s² tới 1 m/s | (m·a + F_c,tổng)·v = (9,7 + 4,76)·1 ≈ 14,5 W tổng, ≈ 3,6 W mỗi động cơ | 26,7 W mỗi động cơ |
| Cận trên khi cả 4 bánh tải xấu nhất ở 25 rad/s | 0,357 × 25 ≈ 8,9 W mỗi động cơ | 33% của 26,7 W |
| Dòng điện tại 0,357 N·m | ≈ 0,4 + 21,7 × (0,357/6,28) ≈ 1,6 A | ≤ 2,9 A định mức |

---

## 10. Kết luận

1. **Hình học lực:** rank(B) = 3 nên bốn động cơ tạo được mọi tổ hợp (Fx, Fy, Mz), robot chạy được đa hướng.
2. **Lực/mô-men:** lực cần xấu nhất 23,8 N so với khả năng 73,7 N; mô-men xấu nhất trên một bánh 0,357 N·m so với 0,981 N·m định mức.
3. **Công suất, dòng điện:** đều dưới giới hạn định mức với dư địa lớn.
4. **Tốc độ:** tối đa lý thuyết khoảng **1,6 m/s**, thực tế nên dùng **1,4 – 1,5 m/s**.

Vậy 4 động cơ MD36L P27 24 V **đủ lực để chạy robot Mecanum nặng 9,7 kg** theo mô hình động lực học này.

### Lưu ý và hạn chế

- Các giá trị r, L + d, Iz, μ_r và gia tốc yêu cầu là **giả định**; cần thay bằng số đo thật.
- Mã E01122799 chưa được xác nhận trùng với MD36L P27 24 V; cần đối chiếu nhãn động cơ.
- Gia tốc thực tế bị giới hạn bởi độ bám của con lăn (khoảng 14 N mỗi bánh nếu μ_s ≈ 0,6, tương ứng a ≈ 5,9 m/s²), thấp hơn khả năng của động cơ.
- Mô hình bỏ qua quán tính bánh và trượt con lăn; khi đi ngang, tốc độ thực tế của bánh Mecanum thường thấp hơn lý thuyết.
- Đường đặc tính tốc độ–mô-men được xấp xỉ tuyến tính từ ba điểm trên nhãn (không tải, định mức, stall).
