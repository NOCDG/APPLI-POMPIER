import React from "react";
import ReactQuill from "react-quill";

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  height?: number | string;
};

const modules = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline", "strike"],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ align: [] }],
    ["link"],
    ["clean"],
  ],
};

const formats = [
  "header",
  "bold", "italic", "underline", "strike",
  "list", "bullet",
  "align",
  "link",
];

export default function HtmlEditor({ value, onChange, placeholder, height = 180 }: Props) {
  return (
    <div className="html-editor" style={{ background:"#0b0f20", border:"1px solid #2e3a66", borderRadius:10 }}>
      <ReactQuill
        theme="snow"
        value={value || ""}
        onChange={onChange}
        placeholder={placeholder}
        modules={modules}
        formats={formats}
      />
      <style>{`
        .ql-toolbar.ql-snow { border: none; border-bottom: 1px solid #2e3a66; background:#0d1226; }
        .ql-container.ql-snow { border: none; min-height:${typeof height === "number" ? `${height}px` : height}; background:#0b0f20; color:#e9eeff; }
        .ql-snow .ql-picker { color:#e9eeff; }
        .ql-snow .ql-stroke { stroke:#e9eeff; }
        .ql-snow .ql-fill, .ql-snow .ql-stroke.ql-fill { fill:#e9eeff; }
        .ql-editor a { color:#9ec1ff; }
      `}</style>
    </div>
  );
}
