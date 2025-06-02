from transformers import BlipProcessor, BlipForConditionalGeneration
import gradio as gr
from PIL import Image
import requests
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
def generate_caption(image):
    inputs = processor(image, return_tensors="pt")
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption
gr.Interface(
    fn=generate_caption,
    inputs=gr.Image(type="pil"),
    outputs="text",
    title="🖼️ AI Image Caption Generator",
    description="Upload an image and let the AI describe it!"
).launch()