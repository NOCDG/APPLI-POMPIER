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
    <div className="html-editor" style={{ background:"var(--surface-3)", border:"1px solid var(--border)", borderRadius:10 }}>
      <ReactQuill
        theme="snow"
        value={value || ""}
        onChange={onChange}
        placeholder={placeholder}
        modules={modules}
        formats={formats}
      />
      <style>{`
        .ql-toolbar.ql-snow { border: none; border-bottom: 1px solid var(--border); background:var(--surface-2); }
        .ql-container.ql-snow { border: none; min-height:${typeof height === "number" ? `${height}px` : height}; background:var(--surface-3); color:var(--text); }
        .ql-snow .ql-picker { color:var(--text); }
        .ql-snow .ql-stroke { stroke:var(--text-subtle); }
        .ql-snow .ql-fill, .ql-snow .ql-stroke.ql-fill { fill:var(--text-subtle); }
        .ql-editor a { color:var(--accent); }
      `}</style>
    </div>
  );
}
