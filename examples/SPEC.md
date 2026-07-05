# Bản định nghĩa chức năng｜Công cụ tạo "Báo cáo hoạt động bán bất động sản"

Công cụ hỗ trợ tạo file PDF "Báo cáo hoạt động bán" gửi cho bên bán, tuân theo Luật Nghiệp vụ giao dịch bất động sản (Takken-gyō-hō) của Nhật Bản. Tài liệu này chỉ định nghĩa các logic chính sau đây.

---

## 1. Luồng trải nghiệm người dùng (UX)

1. Bắt đầu sử dụng **không cần đăng nhập**
2. **Đăng ký thông tin công ty** (địa chỉ công ty, số giấy phép, v.v.) → dùng cho cả việc ghi vào báo cáo lẫn việc trích xuất bất động sản môi giới
3. **Lấy bất động sản môi giới** (trích xuất các BĐS đang đăng từ bảng `sale_`) → chọn từ danh sách. Nếu không có kết quả phù hợp thì nhập tay
4. **Nhập ngày ký hợp đồng và loại hợp đồng môi giới** → kỳ báo cáo được xác định tự động (không cần nhập tay)
5. **Nhập thông tin phản hồi** (ghi PV / phản hồi / lượt xem nhà theo đơn vị tuần)
6. **Tự động tạo bảng tổng hợp phản hồi và biểu đồ**
7. Ghi nhận định và đề xuất bán hàng rồi **xuất PDF**
8. Với các báo cáo cũ, có thể **xuất lại / nhân bản** từ danh sách

---

## 2. Logic lấy bất động sản môi giới

- Dùng **địa chỉ công ty + số giấy phép** trong thông tin công ty làm khóa, trích xuất các **BĐS đang đăng (đang trong hợp đồng môi giới)** từ **bảng `sale_`** của Pinrich
- Hiển thị kết quả trích xuất dưới dạng danh sách, chọn BĐS mục tiêu
- Nếu không có BĐS phù hợp thì nhập tay
- Nếu thông tin công ty (địa chỉ, số giấy phép) chưa được đăng ký thì không thể trích xuất BĐS

**Hiển thị cấu trúc hóa địa chỉ**

- Sau khi nhập địa chỉ, **hiển thị kết quả cấu trúc hóa ở phía dưới ô nhập với cỡ chữ nhỏ (dưới dạng text bổ trợ)**
- Các trường được hiển thị và lưu giữ: `prefecture_name` (tỉnh/thành – tô-đô-fu-ken) / `location_name_1` (quận/huyện/thị xã) / `town` (khu phố, số nhà)
    - Ví dụ: "東京都港区恵比寿４丁目" → `prefecture_name` = Tokyo / `location_name_1` = quận Minato / `town` = Ebisu 4-chome
- Lưu giữ các giá trị đã cấu trúc hóa và dùng để đối chiếu (matching) với bảng `sale_`

---

## 3. Logic xác định kỳ báo cáo

- Từ **loại hợp đồng môi giới + ngày ký hợp đồng**, kỳ báo cáo được xác định tự động (không để người dùng nhập tay)
- Lấy **ngày ký hợp đồng làm mốc bắt đầu của tuần thứ 1**, quản lý theo thời hạn hợp đồng **3 tháng = 13 tuần**

| Loại hợp đồng môi giới | Kỳ báo cáo |
| --- | --- |
| Môi giới độc quyền chuyên trách (senzoku-sennin) | **1 tuần** |
| Loại khác (chuyên trách / thông thường / đại lý) | **2 tuần** |

**Cách đếm tuần**

- Tuần được đếm **theo từng 7 ngày kể từ ngày mốc (ngày ký hợp đồng)**
- **Kể cả khi vượt quá tuần thứ 13, hoặc trong trường hợp đơn vị 2 tuần (chuyên trách / thông thường / đại lý), vẫn đếm theo bước 7 ngày kể từ ngày mốc**, và **tuần cuối cùng có thể ít hơn hoặc bằng 7 ngày (phần lẻ)**

**Phán định 13 tuần / 14 tuần**

- Thời hạn hợp đồng (3 tháng) thông thường là **13 tuần (= 91 ngày)**, nhưng **tùy theo ngày ký hợp đồng, có thể phát sinh tuần thứ 14 (tuần lẻ)**
- Tiêu chí phán định là **"số ngày tính đến ngày tương ứng (ứng-đáng-nhật) sau 3 tháng kể từ ngày ký hợp đồng"**
    - 13 tuần = 91 ngày. **Khi số ngày này trở thành 92 ngày thì phát sinh tuần thứ 14** (từ 1 ngày lẻ trở lên)
    - Số ngày này được quyết định bởi **tổng số ngày dương lịch của 3 tháng liên tiếp tính từ tháng ký hợp đồng** (ví dụ: khởi điểm tháng 3 = tháng 3 + tháng 4 + tháng 5 = 92 ngày), và về nguyên tắc **được quyết định bởi "tháng" của ngày ký hợp đồng** (không phụ thuộc vào ngày)
    - Ngoại lệ: **ngày cuối tháng thì ngày tương ứng sau 3 tháng bị dời sớm lên (clamp)**, nên có những ngày quay về 13 tuần (ví dụ: 31/3 → 30/6 là 91 ngày = 13 tuần)
- **Không phát sinh từ tuần thứ 15 trở lên** (vì tổng tối đa của 3 tháng liên tiếp là 92 ngày)

**Các ngày ký hợp đồng phát sinh tuần thứ 14 (định nghĩa đầy đủ)**

| Tháng của ngày ký | Ngày trở thành 14 tuần | Ghi chú |
| --- | --- | --- |
| **Tháng 3** | **Ngày 1 – 30** | 31/3 là 13 tuần (clamp về 30/6) |
| **Tháng 5** | **Ngày 1 – 31 (toàn bộ)** | — |
| **Tháng 6** | **Ngày 1 – 30 (toàn bộ)** | — |
| **Tháng 7** | **Ngày 1 – 31 (toàn bộ)** | — |
| **Tháng 8** | **Ngày 1 – 30** | 31/8 là 13 tuần (clamp về 30/11) |
| **Tháng 10** | **Ngày 1 – 31 (toàn bộ)** | — |
| **Tháng 11** | **Ngày 1 – 28** | 30/11 là 13 tuần. **29/11 chỉ là 14 tuần khi tháng 2 năm sau là năm nhuận** (năm thường là 13 tuần) |

- Các tháng ngoài bảng trên (**tháng 1, 2, 4, 9, 12**) đều là 13 tuần cho tất cả các ngày
- Năm nhuận không làm thay đổi phán định. Ngoại lệ duy nhất là **ngày 29/11** (chỉ 14 tuần trong năm mà tháng 2 tương ứng là năm nhuận, tức có ngày 29/2)

---

## 4. Nhập thông tin phản hồi

- Với mỗi tuần × mỗi kênh truyền thông, nhập **PV / phản hồi / lượt xem nhà**
- **Luôn luôn nhập theo đơn vị "1 tuần" bất kể loại hợp đồng** (cố định 13 tuần; kể cả khi kỳ báo cáo là 2 tuần thì việc nhập vẫn theo đơn vị tuần)
- Cho phép hiển thị và ghi đến tuần mà ngày cuối tuần chưa đến vào hôm nay (tức tuần đang diễn ra). **Từ tuần kế tiếp trở đi sẽ bị làm mờ (grayout) và không cho ghi** (tức tự động phán định tuần hiện tại)

---

## 5. Tổng hợp biểu đồ phản hồi và bảng tóm tắt

Độ phân giải (mesh) của biểu đồ được chia riêng giữa **màn hình nhập liệu** và **báo cáo xuất ra (PDF)**. Bảng tóm tắt trong cả hai trường hợp đều tổng hợp theo kỳ báo cáo.

| Phân loại | Biểu đồ phản hồi | Tóm tắt (chỉ số) |
| --- | --- | --- |
| Màn hình nhập liệu (hiển thị trong app) | **Luôn theo đơn vị 1 tuần** (cố định bất kể loại hợp đồng) | Tổng hợp theo kỳ báo cáo |
| Báo cáo xuất ra (PDF) | **Mesh theo kỳ báo cáo**: độc quyền chuyên trách = 1 tuần / loại khác = 2 tuần | Tổng hợp theo kỳ báo cáo |

- Độ rộng tổng hợp của phần tóm tắt (chỉ số) thay đổi theo từng loại hợp đồng môi giới

| Loại hợp đồng môi giới | Độ rộng tóm tắt / Mesh biểu đồ trong báo cáo |
| --- | --- |
| Môi giới độc quyền chuyên trách | **1 tuần** |
| Loại khác (chuyên trách / thông thường / đại lý) | **2 tuần** |

- Dữ liệu nhập theo đơn vị tuần được cộng dồn theo kỳ báo cáo để tính ra các giá trị tóm tắt (kỳ báo cáo / lũy kế / so với kỳ trước)
- **Biểu đồ phản hồi của báo cáo xuất ra được tạo với mesh 1 tuần (độc quyền chuyên trách) / mesh 2 tuần (loại khác)** (gom các giá trị nhập theo tuần thành từng kỳ báo cáo để vẽ)
- Biểu đồ và bảng theo tuần trên màn hình nhập liệu luôn giữ theo đơn vị tuần (phục vụ nhập và kiểm tra dữ liệu)

### Trường hợp không có kênh đăng tin

- Nếu trong kỳ báo cáo mục tiêu **không có kênh nào đăng tin (không có ghi nhận), thì bỏ qua phần tóm tắt phản hồi**
- **Không tạo trang phản hồi (biểu đồ, tóm tắt) trong báo cáo xuất ra (PDF)**
- Các hạng mục báo cáo khác ngoài kênh truyền thông (như tình trạng đăng ký REINS) vẫn được xử lý như bình thường

---

## 6. Hành vi khi nhân bản

Việc nhân bản có hành vi khác nhau tùy theo thời hạn hợp đồng (3 tháng = 13 tuần) **đang tiếp diễn hay đã kết thúc**.

| Thời điểm nhân bản | Bước bắt đầu | Trạng thái phản hồi |
| --- | --- | --- |
| **Thời hạn hợp đồng đang tiếp diễn** (giữa 13 tuần) | Bắt đầu lại từ bước nhập phản hồi | Kế thừa các tuần đã nhập lần trước. Bổ sung tuần vừa đến trong lần này |
| **Sau khi hết 3 tháng (13 tuần)** | Làm lại từ bước nhập kỳ (ngày ký hợp đồng) | Bắt đầu lại từ tuần thứ 1 (chu kỳ mới) |

- **Nhân bản khi đang tiếp diễn**: các tuần phản hồi đã nhập đến lần trước được hiển thị ở trạng thái đã nhập. Trong số các tuần lần trước chưa đến, những tuần đã đến trong lần này sẽ trở nên có thể ghi
- **Nhân bản sau khi hết 3 tháng**: tương đương với việc gia hạn hợp đồng môi giới (3 tháng mới), nên tạo lại 13 tuần lấy ngày ký hợp đồng mới làm mốc và nhập lại từ tuần thứ 1 (không kế thừa phản hồi của chu kỳ trước)

---

## 7. Sinh nội dung bằng AI cho nhận định và đề xuất bán hàng

Tự động sinh "nhận định của người phụ trách" và "đề xuất bán hàng" bằng AI. Nội dung được sinh ra có thể chỉnh sửa. Chỉ khi cả hai đều được nhập thì báo cáo mới có thể được xác nhận (chốt).

| Hạng mục | Nguồn đầu vào cho AI sinh nội dung | Đặc tả |
| --- | --- | --- |
| Nhận định của người phụ trách | Thông tin BĐS + thời gian bán + giá + thông tin phản hồi + tình trạng xem nhà + tình trạng thương lượng | Văn phong lịch sự (desu/masu) / 180–230 ký tự |
| Đề xuất bán hàng | Nhận định của người phụ trách + dữ liệu BĐS cạnh tranh (+ tham khảo xem nhà, thương lượng) | Văn phong lịch sự (desu/masu) / 200–250 ký tự |

> Sinh theo thứ tự nhận định → đề xuất. Đề xuất bán hàng đưa nhận định đã sinh và chỉnh sửa (`{{nhan_dinh_ban_van}}`) vào phần đầu vào để đảm bảo tính nhất quán.

### Các biến chèn (placeholder)

| Biến | Nội dung |
| --- | --- |
| `{{ten_bds}}` `{{loai_hinh}}` `{{bo_tri_phong}}` `{{dien_tich}}` `{{tang}}` | Thuộc tính BĐS |
| `{{gia_rao_ban}}` | Giá rao bán (đơn vị man-yên) |
| `{{thoi_gian_ban}}` | Thời gian từ ngày bắt đầu rao bán đến hôm nay, kỳ báo cáo |
| `{{PV_ky_bao_cao}}` `{{PV_luy_ke}}` `{{PV_so_ky_truoc}}` | Lượt xem |
| `{{phan_hoi_ky_bao_cao}}` `{{phan_hoi_luy_ke}}` `{{phan_hoi_so_ky_truoc}}` | Phản hồi |
| `{{so_luot_xem_nha}}` `{{ghi_chu_xem_nha}}` | Xem nhà (ngày, nguồn phản hồi, khách hàng, ghi chú nhận định) |
| `{{so_thuong_luong}}` `{{tinh_trang_thuong_luong}}` | Thương lượng giá (trả giá, kế hoạch tài chính, tiến độ) |
| `{{vi_du_canh_tranh}}` | Danh sách tên trường hợp, diện tích, bố trí phòng, giá, đơn giá /m² |
| `{{ty_le_so_binh_quan_canh_tranh}}` | Chênh lệch (%) giữa đơn giá /m² của BĐS mục tiêu và bình quân cạnh tranh |
| `{{nhan_dinh_ban_van}}` | Nhận định của người phụ trách đã sinh và chỉnh sửa |

### Prompt ①: Nhận định của người phụ trách

```
Bạn là người phụ trách môi giới bất động sản. Hãy soạn phần nội dung "nhận định của người phụ trách nhìn lại hoạt động bán trong kỳ này" bằng tiếng Nhật, để đệ trình cho bên bán.
Tổng kết hoạt động bán trong kỳ này và tổng hợp thành lời bình gửi tới bên bán. Hãy lồng ghép các quan điểm sau vào một đoạn văn tự nhiên, trong phạm vi các sự thật được cung cấp.

- Diễn biến của phản hồi (lượt xem, hỏi thông tin) và so sánh với kỳ trước
- Tình trạng xem nhà (số lượt, phản ứng của người đến xem, những điểm được đánh giá cao hoặc lo ngại)
- Tình trạng thương lượng giá (trả giá, mức độ tiến triển của việc cân nhắc)
- Những điểm được đánh giá cao của BĐS và phản ứng của bên mua về giá

【Điều kiện đầu ra】
- Khoảng 180–230 ký tự, văn phong lịch sự (desu/masu)
- Không cần lời dẫn, tiêu đề, gạch đầu dòng; chỉ xuất phần nội dung
- Không viết các con số không có thật hay cam kết chốt giao dịch. Dùng cách diễn đạt lịch sự, chu đáo với bên bán
- Với hạng mục không có dữ liệu (ví dụ: 0 lượt xem nhà), không cố đề cập; tổng hợp tập trung vào thông tin đang có

【BĐS mục tiêu】{{ten_bds}}（{{loai_hinh}}／{{bo_tri_phong}}／{{dien_tich}}／{{tang}}）／Giá rao bán {{gia_rao_ban}}
【Thời gian bán】{{thoi_gian_ban}}
【Phản hồi】Kỳ báo cáo: lượt xem {{PV_ky_bao_cao}}PV（so kỳ trước {{PV_so_ky_truoc}}）・phản hồi {{phan_hoi_ky_bao_cao}} lượt（so kỳ trước {{phan_hoi_so_ky_truoc}}）／Lũy kế: lượt xem {{PV_luy_ke}}PV・phản hồi {{phan_hoi_luy_ke}} lượt
【Xem nhà】{{so_luot_xem_nha}} lượt
{{ghi_chu_xem_nha}}
【Thương lượng giá】{{so_thuong_luong}} lượt
{{tinh_trang_thuong_luong}}
```

### Prompt ②: Đề xuất bán hàng

```
Bạn là người phụ trách môi giới bất động sản. Hãy soạn phần nội dung "đề xuất bán hàng cho kỳ báo cáo tiếp theo" bằng tiếng Nhật, để đệ trình cho bên bán.
Dựa trên nhận định của người phụ trách trong kỳ này và việc so sánh giá, đơn giá /m² với các BĐS cạnh tranh lân cận, hãy đề xuất cụ thể chiến lược giá và các biện pháp xúc tiến bán. Cũng đưa tình trạng xem nhà, thương lượng vào làm căn cứ phán đoán.

- Chiến lược giá: dựa trên tỷ lệ so với bình quân cạnh tranh（{{ty_le_so_binh_quan_canh_tranh}}）làm căn cứ, đưa ra phương châm giữ giá / điều chỉnh giá
- Biện pháp xúc tiến: đề xuất những biện pháp phù hợp trong số làm mới ảnh, cải thiện lời quảng cáo, open house, bổ sung kênh truyền thông, v.v.
- Nếu có trường hợp đang thương lượng, đưa vào nội dung ưu tiên chốt (closing) trường hợp đó

【Điều kiện đầu ra】
- Khoảng 200–250 ký tự, văn phong lịch sự (desu/masu)
- Không cần lời dẫn, tiêu đề, gạch đầu dòng; chỉ xuất phần nội dung
- Dựa trên căn cứ so sánh cạnh tranh, đưa ra đề xuất thực tế và khả thi. Không cam kết chốt giao dịch

【Nhận định của người phụ trách】{{nhan_dinh_ban_van}}
【BĐS mục tiêu】{{ten_bds}}／Giá rao bán {{gia_rao_ban}}／{{dien_tich}}
【Ví dụ cạnh tranh】
{{vi_du_canh_tranh}}
【Tỷ lệ so bình quân cạnh tranh】Đơn giá /m² của BĐS mục tiêu so với bình quân cạnh tranh là {{ty_le_so_binh_quan_canh_tranh}}
【Tình trạng xem nhà, thương lượng】Xem nhà {{so_luot_xem_nha}} lượt／Thương lượng {{so_thuong_luong}} lượt（{{tinh_trang_thuong_luong}}）
```
