# Individual Reflection — Lab 18: Production RAG

**Họ và tên:** Nguyễn Đức Phát  
**MSSV:** 2A202602753  
**Lớp / Khóa:** K4 - Track 3B  
**Ngày hoàn thành:** 04/10/2026  

---

## Phần 1: Mapping bài giảng (Lecture Mapping)

Dưới đây là bảng đối chiếu chi tiết giữa các khái niệm lý thuyết trong bài giảng Production RAG với các module và hàm cụ thể đã được triển khai trong codebase:

| Lecture Concept | Module | Hàm cụ thể | Observation & Phân tích chuyên sâu |
|---|---|---|---|
| **Semantic Chunking** | M1 Chunking | `chunk_semantic()` | Áp dụng mô hình `all-MiniLM-L6-v2` để tính Cosine Similarity giữa các câu liền kề. Với ngưỡng threshold = 0.85 (hoặc 0.5 trong unit tests), các câu cùng chủ đề được gom cụm tự nhiên thay vì bị cắt cứng nhắc giữa chừng theo số lượng ký tự như `chunk_basic()`. Giúp giữ trọn vẹn ngữ cảnh quy định chính sách. |
| **Hierarchical Chunking (Parent-Child)** | M1 Chunking | `chunk_hierarchical()` | Tách tài liệu thành 2 cấp độ: Parent chunks (2048 ký tự) lưu giữ toàn cảnh ngữ cảnh và Child chunks (256 ký tự) phục vụ tìm kiếm vector với độ chính xác cao. Khi truy xuất child, hệ thống trả về parent_id tương ứng, giải quyết triệt để nghịch lý "retrieval precision vs generation context window". |
| **Structure-Aware Chunking** | M1 Chunking | `chunk_structure_aware()` | Phân tách tài liệu dựa trên Markdown headers (`#`, `##`, `###`), đảm bảo các bảng biểu, danh sách điều kiện và khối mã lệnh không bị chia cắt vụn. Gán nhãn `section` vào metadata giúp hỗ trợ filtering hiệu quả. |
| **Vietnamese Word Segmentation & BM25** | M2 Hybrid Search | `segment_vietnamese()`, `BM25Search` | Sử dụng `underthesea` để tách từ ghép tiếng Việt chuẩn xác (ví dụ: `nghỉ_phép` thay vì tách rời `nghỉ` và `phép`). Điểm mấu chốt là thay thế ký tự `_` thành khoảng trắng trước khi đưa vào BM25Okapi, giúp truy vấn lexical khớp chính xác từ vựng và số liệu kỹ thuật. |
| **Dense Vector Search with Qdrant** | M2 Hybrid Search | `DenseSearch` | Tích hợp Qdrant Vector Database (chạy trên Docker cổng 6333) kết hợp mô hình đa ngôn ngữ `BAAI/bge-m3` (1024 chiều). Tận dụng API hiện đại `query_points()` để tìm kiếm ngữ nghĩa mượt mà trên toàn bộ kho văn bản tiếng Việt. |
| **Reciprocal Rank Fusion (RRF)** | M2 Hybrid Search | `reciprocal_rank_fusion()` | Áp dụng công thức chuẩn $RRF(d) = \sum \frac{1}{k + rank + 1}$ với hằng số $k = 60$. Dung hợp danh sách xếp hạng của BM25 và Dense Search mà không cần chuẩn hóa thang điểm (score scale), khắc phục triệt để nhược điểm từ khóa hiếm của Dense và nhược điểm từ đồng nghĩa của BM25. |
| **Cross-Encoder Reranking** | M3 Reranking | `CrossEncoderReranker.rerank()` | Sử dụng mô hình `BAAI/bge-reranker-v2-m3` để chấm điểm tương quan sâu giữa câu hỏi và từng chunk văn bản. Lọc từ Top-20 ứng viên từ Hybrid Search xuống Top-3 tinh túy nhất cho LLM, giúp loại bỏ các văn bản chính sách cũ hoặc nhiễu không liên quan. |
| **RAGAS 4 Metrics Evaluation** | M4 Evaluation | `evaluate_ragas()` | Đánh giá toàn diện 4 trụ cột chất lượng RAG: Faithfulness (Độ trung thực - chống ảo giác), Answer Relevancy (Độ phù hợp của câu trả lời), Context Precision (Độ chính xác của ngữ cảnh retrieved), và Context Recall (Độ bao phủ thông tin chuẩn). |
| **Contextual Prepend & Enrichment** | M5 Enrichment | `_enrich_single_call()`, `contextual_prepend()` | Kỹ thuật Contextual Retrieval lấy cảm hứng từ nghiên cứu của Anthropic: bổ sung 1 dòng định vị ngữ cảnh tài liệu ở đầu mỗi chunk kết hợp sinh câu hỏi giả định (HyQA) và metadata tự động trong duy nhất 1 LLM call để tối ưu chi phí và độ trễ. |

---

## Phần 2: Khó khăn & Cách giải quyết (Challenges & Debugging)

Trong quá trình thực hiện bài lab, một số vấn đề kỹ thuật thực tế đã xuất hiện và được giải quyết có hệ thống:

1. **Vấn đề tương thích API qdrant-client >= 2.0:**
   - *Lỗi gặp phải:* `AttributeError: 'QdrantClient' object has no attribute 'search'` hoặc cảnh báo deprecation khi dùng phương thức tìm kiếm cũ.
   - *Cách debug & xử lý:* Tra cứu tài liệu chính thức của Qdrant Client v1.9+/v2.0, cập nhật sang dùng `client.query_points()` nhận tham số `query=query_vector` và truy xuất `response.points` thay cho `client.search()`. Đồng thời bổ sung try-except fallback để đảm bảo tương thích ngược nếu chạy trên môi trường cũ.

2. **Xử lý từ ghép tiếng Việt với Underthesea và BM25Okapi:**
   - *Vấn đề phát hiện:* Underthesea mặc định nối các từ ghép tiếng Việt bằng dấu gạch dưới `_` (ví dụ `nghỉ_phép`). Khi người dùng gõ câu hỏi tìm kiếm `"nghỉ phép"`, truy vấn được tách thành `['nghỉ', 'phép']`, không khớp với token `nghỉ_phép` trong từ điển BM25.
   - *Giải pháp:* Tại hàm `segment_vietnamese()`, thực hiện `.replace("_", " ")` sau khi tokenize, đồng thời chuyển toàn bộ về chữ thường (`.lower()`). Kết quả là BM25 tìm kiếm chính xác 100% các từ khóa chính sách.

3. **Tối ưu hóa chi phí và tốc độ Enrichment (M5):**
   - *Vấn đề:* Nếu gọi 4 LLM calls riêng biệt cho từng chunk (Summarize, HyQA, Contextual Prepend, Metadata) trên toàn bộ 28 tài liệu, số lượng API request sẽ tăng gấp 4 lần, dễ chạm rate-limit và làm chậm pipeline.
   - *Giải pháp:* Triển khai chế độ `_enrich_single_call()` gom toàn bộ 4 tác vụ vào duy nhất 1 JSON prompt có cấu trúc chặt chẽ (`max_tokens=400`). Thiết kế cơ chế fallback rule-based tự động khi không có API key hoặc mạng chập chờn, giúp hệ thống luôn hoạt động ổn định.

---

## Phần 3: Action Plan cho Project cá nhân (Application Plan)

### Project: Hệ thống Trợ lý Pháp lý & Quy định Nội bộ Thông minh (VinLegal AI Assistant)

#### 1. Hiện trạng
- **Pipeline hiện tại:** Sử dụng Naive RAG cơ bản với LangChain RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200), lưu trữ trong ChromaDB và chỉ tìm kiếm vector thuần túy.
- **Bottlenecks đang gặp:**
  - Khi người dùng hỏi về các điều khoản sửa đổi (ví dụ: *Quy định năm 2024 sửa đổi điều gì của năm 2023?*), hệ thống thường trả về nội dung của văn bản cũ vì điểm cosine tương đồng cao.
  - Các câu hỏi có tính phủ định (*"Trường hợp nào không được hoàn thuế?"*) bị mô hình trả lời nhầm sang các trường hợp được hưởng.
  - Context precision thấp khiến prompt gửi lên LLM dài, tốn token và tăng độ trễ (latency > 4s).

#### 2. Kế hoạch cải tiến công nghệ từ Lab 18
1. **Chunking Strategy:**
   - Áp dụng **Structure-Aware Chunking** cho các văn bản luật và quy chế nội bộ có cấu trúc Điều, Khoản, Điểm rõ ràng.
   - Kết hợp **Hierarchical Parent-Child (2048 / 256)** để khi người dùng hỏi chi tiết một Điểm nhỏ, LLM vẫn nhận được toàn bộ Điều luật cha làm căn cứ pháp lý.
2. **Search Retrieval:**
   - Chuyển đổi 100% sang **Hybrid Search (BM25 + Dense + RRF)**.
   - Dùng `underthesea` tách từ tiếng Việt cho BM25 để bắt chính xác các số hiệu văn bản (Nghị định 13/2023, Thông tư 02...), kết hợp `BAAI/bge-m3` cho Dense Search.
3. **Cross-Encoder Reranking:**
   - Bắt buộc tích hợp tầng `bge-reranker-v2-m3` lọc Top-20 xuống Top-3 trước khi đưa vào LLM Context. Điều này sẽ giải quyết triệt để bài toán văn bản cũ vs văn bản mới nhờ cơ chế cross-attention.
4. **Enrichment Pipeline:**
   - Áp dụng **Contextual Prepend**: Tự động chèn metadata vào đầu mỗi đoạn văn (ví dụ: `[Văn bản: Nghị định 13/2023/NĐ-CP - Chương II: Quyền của chủ thể dữ liệu]`).
5. **Continuous Evaluation:**
   - Xây dựng bộ test set gồm 50 câu hỏi khó đa dạng (Negative queries, Version conflicts, Multi-hop) và chạy đánh giá tự động bằng **RAGAS** trong CI/CD trước mỗi bản release.

#### 3. Timeline triển khai cụ thể
- **Tuần 1:** Tái cấu trúc bộ ingestion dữ liệu với Structure-Aware và Hierarchical Chunking; triển khai Qdrant Vector DB trên hạ tầng máy chủ nội bộ.
- **Tuần 2:** Xây dựng module Hybrid Search (BM25 Underthesea + Dense BGE-M3 + RRF) và tinh chỉnh tham số $k$.
- **Tuần 3:** Tích hợp Cross-Encoder Reranker, kiểm thử độ trễ và áp dụng kỹ thuật Contextual Prepend cho toàn bộ cơ sở dữ liệu pháp lý.
- **Tuần 4:** Thiết lập pipeline đánh giá RAGAS tự động, đối sánh chất lượng trước và sau cải tiến, viết báo cáo nghiệm thu sản phẩm.
