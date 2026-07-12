"""Import the user-provided 2026 math papers into private LaTeX assets."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from latex_pipeline import convert_bytes

SOURCE = Path(r"C:\Users\T590\Downloads\2026·高考数学真题")
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "gaokao_2026"

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SOURCE.iterdir() if p.is_file())
    pdf_by_stem = {p.stem: p for p in files if p.suffix.lower()==".pdf"}
    items=[]
    for docx in (p for p in files if p.suffix.lower()==".docx"):
        result=convert_bytes(docx.name, docx.read_bytes(), "")
        target=OUTPUT/(docx.stem+".tex")
        target.write_text(result["latex"],encoding="utf-8")
        normalized=docx.stem.replace("Ⅰ","1").replace("Ⅱ","2")
        region=next((label for key,label in [("上海）（春考","上海春考"),("上海）（秋考","上海秋考"),("全国1卷","全国1卷"),("全国2卷","全国2卷"),("北京卷","北京卷"),("天津","天津卷")] if key in normalized),"其他")
        items.append({"title":docx.stem,"subject":"高中数学","year":2026,"region":region,"edition":"解析卷" if "解析卷" in docx.stem else "空白卷","latex_file":target.name,"source_docx":docx.name,"source_pdf":pdf_by_stem.get(docx.stem).name if docx.stem in pdf_by_stem else None,"engine":result["engine"],"private":True,"formula_review_required":result["requires_formula_review"],"embedded_formula_images":result.get("embedded_formula_images",0)})
    manifest={"name":"2026高考数学真题私有库","count":len(items),"original_file_count":len(files),"items":items,"notice":"用户提供资料；仅限授权范围内教学使用，不对外公开原文件。"}
    (OUTPUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"converted":len(items),"originals":len(files),"output":str(OUTPUT)},ensure_ascii=False))

if __name__=="__main__": main()
