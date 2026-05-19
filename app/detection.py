from typing import List
import os

import cv2  # type: ignore
import numpy as np
from PIL import Image

import threading

from app.models import QRLocation

_thread_local = threading.local()

def get_wechat_detector():
    """Get or create a thread-local instance of WeChatQRCode to prevent concurrency bugs."""
    if not hasattr(cv2, 'wechat_qrcode_WeChatQRCode'):
        return None
        
    if not hasattr(_thread_local, 'wechat_detector'):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(base_dir, 'wechat_models')
            _thread_local.wechat_detector = cv2.wechat_qrcode_WeChatQRCode(
                os.path.join(model_dir, 'detect.prototxt'),
                os.path.join(model_dir, 'detect.caffemodel'),
                os.path.join(model_dir, 'sr.prototxt'),
                os.path.join(model_dir, 'sr.caffemodel')
            )
        except Exception as e:
            print(f"Warning: Failed to initialize WeChatQRCode detector: {e}")
            _thread_local.wechat_detector = None
            
    return _thread_local.wechat_detector

def get_standard_detector():
    """Get or create a thread-local instance of QRCodeDetector."""
    if not hasattr(_thread_local, 'standard_detector'):
        _thread_local.standard_detector = cv2.QRCodeDetector()
    return _thread_local.standard_detector


def identify_payment_provider(data: str) -> str | None:
    """Analyze EMVCo QR code payload (PHQR) to identify payment provider."""
    if not data.startswith("000201"):
        return None
        
    data_upper = data.upper()
    if "GCASH" in data_upper or "GXCHPH" in data_upper or "GXI" in data_upper:
        return "GCash"
    if "MAYA" in data_upper or "PAYMAYA" in data_upper:
        return "Maya"
    if "BPI" in data_upper:
        return "BPI"
    if "GOTYME" in data_upper:
        return "GoTyme"
    if "UNIONBANK" in data_upper:
        return "UnionBank"
    if "BDO" in data_upper:
        return "BDO"
    if "METROBANK" in data_upper:
        return "Metrobank"
    if "RCBC" in data_upper:
        return "RCBC"
    if "SECURITY BANK" in data_upper:
        return "Security Bank"
    if "INSTAPAY" in data_upper:
        return "InstaPay"
    if "PESONET" in data_upper:
        return "PESONET"
        
    return "Unknown PHQR Provider"


def detect_qr_in_image(img_array: np.ndarray, source_label: str) -> List[QRLocation]:
    """Run QR detection using WeChatQRCode (primary) and standard OpenCV (fallback)."""
    results: List[QRLocation] = []
    seen_data = set()
    
    # 1. Try WeChatQRCode first (extremely robust against logos like GCash/InstaPay)
    wechat_detector = get_wechat_detector()
    if wechat_detector is not None:
        try:
            res, pts = wechat_detector.detectAndDecode(img_array)
            if res and pts:
                for data, pt in zip(res, pts):
                    if data and data not in seen_data:
                        pt_int = np.array(pt, dtype=int).reshape(-1, 2)
                        x = int(pt_int[:, 0].min())
                        y = int(pt_int[:, 1].min())
                        w = int(pt_int[:, 0].max() - x)
                        h = int(pt_int[:, 1].max() - y)
                        results.append(QRLocation(
                            source=source_label,
                            bounding_box={"x": x, "y": y, "width": w, "height": h},
                            data=data,
                            payment_provider=identify_payment_provider(data)
                        ))
                        seen_data.add(data)
        except Exception:
            pass

    # 2. Try OpenCV Multi-QR detection if WeChat missed something
    standard_detector = get_standard_detector()
    try:
        retval, decoded_list, points_list, _ = standard_detector.detectAndDecodeMulti(img_array)
        if retval and decoded_list:
            for data, pts in zip(decoded_list, points_list):
                if data and data not in seen_data:
                    pts_int = pts.astype(int).reshape(-1, 2)
                    x = int(pts_int[:, 0].min())
                    y = int(pts_int[:, 1].min())
                    w = int(pts_int[:, 0].max() - x)
                    h = int(pts_int[:, 1].max() - y)
                    results.append(QRLocation(
                        source=source_label,
                        bounding_box={"x": x, "y": y, "width": w, "height": h},
                        data=data,
                        payment_provider=identify_payment_provider(data)
                    ))
                    seen_data.add(data)
    except Exception:
        pass

    # 3. Fallback: single QR detection (OpenCV)
    if not results:
        data, pts, _ = standard_detector.detectAndDecode(img_array)
        if data and pts is not None and data not in seen_data:
            pts_int = pts.astype(int).reshape(-1, 2)
            x = int(pts_int[:, 0].min())
            y = int(pts_int[:, 1].min())
            w = int(pts_int[:, 0].max() - x)
            h = int(pts_int[:, 1].max() - y)
            results.append(QRLocation(
                source=source_label,
                bounding_box={"x": x, "y": y, "width": w, "height": h},
                data=data,
                payment_provider=identify_payment_provider(data)
            ))

    return results


def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL image to OpenCV BGR numpy array, handling RGBA transparency correctly."""
    if pil_img.mode == "RGBA":
        # Composite onto white background — transparency can break QR decoding
        background = Image.new("RGB", pil_img.size, (255, 255, 255))
        background.paste(pil_img, mask=pil_img.split()[3])  # use alpha as mask
        pil_img = background
    else:
        pil_img = pil_img.convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def risk_level(count: int) -> str:
    if count == 0:
        return "LOW"
    if count <= 2:
        return "MEDIUM"
    return "HIGH"