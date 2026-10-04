# Failure Analysis — Lab 18: Production RAG

**Họ và tên học viên:** Nguyễn Đức Phát  
**MSSV:** 2A202602753  
**Khóa:** K4 - Track 3B  

---

## RAGAS Scores

| Metric | Naive Baseline | Production | Δ |
|--------|---------------|------------|---|
| Faithfulness | 0.8156 | 0.8354 | +0.0198 |
| Answer Relevancy | 0.7849 | 0.8080 | +0.0231 |
| Context Precision | 0.7500 | 0.7500 | +0.0000 |
| Context Recall | 0.6763 | 0.7281 | +0.0518 |

---

## Bottom-5 Failures

### #1
- **Question:** Bao lâu phải đổi mật khẩu một lần?
- **Expected:** Theo chính sách hiện hành (v2.0), mật khẩu phải được thay đổi mỗi 120 ngày. Chính sách cũ yêu cầu 90 ngày nhưng đã bị thay thế.
- **Got:** Tài liệu bao_mat_su_co.md: Trích dẫn quy định liên quan. Khi phát hiện hoặc nghi ngờ sự cố bảo mật, nhân viên phải báo cáo trong vòng 1 giờ qua email helpdesk@cty.vn hoặc hotline CNTT nội bộ...
- **Worst metric:** Context Recall (0.3417)
- **Error Tree:** Output sai → Context sai (retrieval lấy nhầm tài liệu `bao_mat_su_co.md` thay vì `chinh_sach_mat_khau_v2.md`) → Query "đổi mật khẩu" có semantic overlap với các sự cố an toàn thông tin chung.
- **Root cause:** Từ khóa "mật khẩu" bị nhiễu bởi tài liệu sự cố CNTT; BM25 và Dense Search chưa phân biệt rõ giữa văn bản chính sách mật khẩu và quy trình xử lý vi phạm bảo mật.
- **Suggested fix:** Áp dụng Metadata Filtering theo phân loại nghiệp vụ (`category: credential_policy` vs `category: security_incident`), tăng trọng số BM25 cho cụm từ chính xác `"đổi mật khẩu"`.

---

### #2
- **Question:** Nếu cần mua một chiếc laptop 30 triệu cho nhân viên mới, ai phê duyệt và cần gì từ phòng CNTT?
- **Expected:** Laptop 30 triệu nằm trong khoảng 5-50 triệu nên cần Giám đốc phòng ban (Director) phê duyệt. Ngoài ra, mua sắm thiết bị CNTT cần có xác nhận cấu hình kỹ thuật từ phòng CNTT trước khi đề xuất. Cần đính kèm ít nhất 3 báo giá vì trên 10 triệu.
- **Got:** Tài liệu dao_tao_noi_bo.md: Trích dẫn quy định liên quan. Nhân viên có thể đăng ký khóa học qua hệ thống Learning Portal và cần phê duyệt của trưởng phòng...
- **Worst metric:** Context Recall (0.3870)
- **Error Tree:** Output sai → Context sai → Query multi-hop kết hợp "laptop 30 triệu" + "phê duyệt" + "phòng CNTT" làm loãng vector embedding.
- **Root cause:** Câu hỏi có 2 khía cạnh độc lập (thẩm quyền tài chính theo hạn mức tiền và quy trình phê duyệt kỹ thuật của phòng CNTT). Tìm kiếm đơn luồng bị hút vào từ khóa chung "phê duyệt của trưởng phòng" trong tài liệu đào tạo.
- **Suggested fix:** Triển khai Sub-query Decomposition (tách thành: 1. Thẩm quyền duyệt mua sắm tài sản 30 triệu; 2. Yêu cầu kỹ thuật từ phòng CNTT khi mua thiết bị máy tính).

---

### #3
- **Question:** Nhân viên tạm ứng 15 triệu, sau 20 ngày mới thanh toán. Bị phạt bao nhiêu?
- **Expected:** Thời hạn thanh toán là 15 ngày. Quá hạn 5 ngày, bị tính phí 2%/tháng trên 15.000.000 VNĐ = 300.000 VNĐ/tháng (tính pro-rata khoảng 50.000 VNĐ cho 5 ngày).
- **Got:** Tài liệu tam_ung.md: Trích dẫn quy định liên quan. Nhân viên có khoản tạm ứng chưa thanh toán sẽ không được phê duyệt tạm ứng mới. ## Phê duyệt Tạm ứng dưới 5.000.000 VNĐ...
- **Worst metric:** Context Recall (0.4154)
- **Error Tree:** Output thiếu thông tin chế tài phạt chậm nộp → Context chỉ lấy được phần đầu về phê duyệt tạm ứng, thiếu đoạn quy định phạt quá hạn.
- **Root cause:** Kích thước child chunk (256 tokens) cắt ngang điều khoản tài chính, khiến phần chế tài xử phạt nằm ở chunk kế tiếp không được rerank đưa vào top-3 context.
- **Suggested fix:** Sử dụng Parent Document Retrieval (trả về toàn bộ Parent chunk 2048 tokens khi child chunk khớp) để giữ nguyên vẹn bối cảnh bảng biểu và chế tài.

---

### #4
- **Question:** Nhân viên được nghỉ bao nhiêu ngày phép năm?
- **Expected:** Theo chính sách hiện hành (v2024), nhân viên được nghỉ 15 ngày phép năm có lương. Chính sách cũ (v2023) là 12 ngày nhưng đã bị thay thế.
- **Got:** Tài liệu nghi_phep_khong_luong.md: Trích dẫn quy định liên quan. Trong thời gian nghỉ không lương, nhân viên không được hưởng lương và các khoản phụ cấp...
- **Worst metric:** Context Recall (0.4600)
- **Error Tree:** Output sai → Context lấy nhầm file `nghi_phep_khong_luong.md` thay vì `nghi_phep_nam_v2024.md`.
- **Root cause:** Từ khóa "nghỉ phép" có tần suất rất cao trong văn bản nghỉ không lương. Dense search nhận diện độ tương tự ngữ nghĩa chung của "chế độ nghỉ phép" mà bỏ sót chi tiết phân biệt "có lương" và "không lương".
- **Suggested fix:** Contextual Enrichment với HyQA (Hypothesis Questions) chỉ rõ các câu hỏi về "phép năm chính thức có lương" cho tài liệu v2024, kết hợp Version Control filter (`status: active`).

---

### #5
- **Question:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?
- **Expected:** Theo chính sách v2024: 15 ngày cơ bản + 3 ngày thâm niên (9÷3=3) = 18 ngày phép. Lương Senior (P3-P4): 20-35 triệu VNĐ/tháng.
- **Got:** Tài liệu nghi_phep_nam_v2024.md: Trích dẫn quy định liên quan. Ví dụ: nhân viên 9 năm thâm niên được 18 ngày phép (15 + 3). ## Quy định sử dụng Phép năm phải được đăng ký trước ít nhất 2 ngày làm việc...
- **Worst metric:** Context Recall (0.5273)
- **Error Tree:** Output trả lời đúng vế ngày phép (18 ngày) nhưng thiếu hoàn toàn vế khoảng lương Senior.
- **Root cause:** Câu hỏi yêu cầu thông tin cross-document từ 2 tài liệu riêng biệt (`nghi_phep_nam_v2024.md` và `chinh_sach_luong.md`). Top-3 context bị chiếm trọn bởi tài liệu nghỉ phép có điểm match từ khóa cao hơn.
- **Suggested fix:** Áp dụng Multi-Hop Retrieval / Cross-document Aggregation hoặc tăng top_k từ 3 lên 5 để dung nạp đủ context từ cả hai văn bản chính sách.

---

## Case Study (cho presentation)

**Question chọn phân tích:**  
*"Nếu cần mua một chiếc laptop 30 triệu cho nhân viên mới, ai phê duyệt và cần gì từ phòng CNTT?"*

**Error Tree walkthrough:**
1. **Output đúng?**  
   → **KHÔNG.** Hệ thống trả về quy trình đăng ký đào tạo nội bộ trên hệ thống Learning Portal do nhầm lẫn từ khóa "phê duyệt".
2. **Context đúng?**  
   → **KHÔNG.** Context được retrieve gồm đoạn trích từ `dao_tao_noi_bo.md` thay vì quy chế mua sắm tài sản và quy định kỹ thuật CNTT.
3. **Query rewrite OK?**  
   → **CHƯA TỐI ƯU.** Câu hỏi chứa 3 thực thể: "laptop 30 triệu", "ai phê duyệt", "phòng CNTT". Khi giữ nguyên raw query, mô hình dense search bị nhiễu bởi các văn bản có nhiều từ khóa hành chính chung.
4. **Fix ở bước:**  
   → **Bước M2 (Query Decomposition) & M5 (Metadata Enrichment):**  
   - M5: Gán metadata `category: procurement` và `category: it_assets` cho các tài liệu mua sắm.  
   - M2: Phân tách query thành 2 truy vấn con độc lập, sau đó hợp nhất kết quả bằng RRF để đảm bảo cả 2 khía cạnh tài chính và kỹ thuật đều xuất hiện trong top context.

**Nếu có thêm 1 giờ, sẽ optimize:**
- **Thử nghiệm Parent Document Retrieval:** Trả về chunk cha (Parent Chunk 2048) cho Generator khi child chunk được chọn bởi Reranker, giúp giải quyết triệt để lỗi mất ngữ cảnh ở các điều khoản phạt tạm ứng (#3).
- **Fine-tune Cross-Encoder Reranker:** Huấn luyện nhẹ mô hình reranker trên bộ dữ liệu Q&A nội bộ tiếng Việt để tăng khả năng phân biệt văn bản thay thế (v2024 vs v2023) và giảm tỷ lệ chọn nhầm tài liệu tương đồng.
- **Thêm cơ chế Multi-hop Query Router:** Tự động phát hiện câu hỏi phức hợp cần tổng hợp từ nhiều tài liệu để kích hoạt chiến lược lấy đa dạng nguồn (Diverse Retrieval).
