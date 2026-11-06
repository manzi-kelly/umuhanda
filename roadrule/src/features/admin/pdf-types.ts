export type PdfDocument = {
  id: string;
  original_filename: string;
  sha256_hash: string;
  file_size_bytes: number;
  page_count: number;
  import_status: string;
  created_at: string;
  error_summary: string | null;
};
export type PdfJob = {
  id: string;
  status: string;
  total_pages: number;
  processed_pages: number;
  extracted_question_count: number;
  review_required_count: number;
  failed_item_count: number;
  diagnostics: {
    code: string;
    page?: number;
    question?: string;
    labels?: string[];
  }[];
};
export type Draft = {
  id: string;
  document_id: string;
  source_question_number: string;
  question_text: string;
  source_page_number: number;
  answer_status: string;
  extraction_status: string;
  options: {
    id: string;
    option_label: string;
    option_text: string;
    source_page_number: number;
  }[];
  answer: {
    selected_option_id: string | null;
    raw_answer_text: string | null;
    evidence_page_number: number | null;
    verification_status: string;
  } | null;
  assets: {
    id: string;
    asset_type: string;
    source_page_number: number;
    source_location?: { option_label?: string };
  }[];
};
export type ResultPage<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
