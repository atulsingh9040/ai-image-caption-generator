"""
Caption Engine: Synthesizes AWS Rekognition labels, categories, and text
into high quality natural language captions, hashtags, and summaries.
Also provides a simulation mode for offline/credential-less testing.
"""
from typing import List, Dict, Any

class CaptionEngine:
    @staticmethod
    def generate_captions_from_rekognition(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        labels = analysis_data.get('labels', [])
        text_detections = analysis_data.get('text_detections', [])
        image_props = analysis_data.get('image_properties', {})

        if not labels:
            return {
                "primary_caption": "An image with no distinct objects identified.",
                "short_caption": "Unidentified scene",
                "detailed_description": "The AWS Rekognition analysis did not return high-confidence labels for this image.",
                "hashtags": [],
                "labels_summary": []
            }

        # Filter & sort labels by confidence
        sorted_labels = sorted(labels, key=lambda x: x.get('Confidence', 0), reverse=True)
        top_labels = [l['Name'] for l in sorted_labels[:10]]
        
        # Categorize labels
        people_labels = []
        animal_labels = []
        activity_labels = []
        environment_labels = []
        object_labels = []

        for l in sorted_labels:
            name = l['Name']
            categories = [c.get('Name', '').lower() for c in l.get('Categories', [])]
            parents = [p.get('Name', '').lower() for p in l.get('Parents', [])]
            
            all_tags = set(categories + parents + [name.lower()])
            
            if any(k in all_tags for k in ['person', 'human', 'people', 'clothing', 'apparel', 'face', 'portrait']):
                people_labels.append(name)
            elif any(k in all_tags for k in ['animal', 'pet', 'wildlife', 'bird', 'dog', 'cat', 'mammal']):
                animal_labels.append(name)
            elif any(k in all_tags for k in ['sport', 'activity', 'running', 'walking', 'jumping', 'working', 'action']):
                activity_labels.append(name)
            elif any(k in all_tags for k in ['outdoors', 'nature', 'landscape', 'architecture', 'building', 'indoor', 'room', 'sky', 'water', 'city']):
                environment_labels.append(name)
            else:
                object_labels.append(name)

        # Detect any prominent text in the image
        prominent_texts = []
        for t in text_detections:
            if t.get('Type') == 'LINE' and t.get('Confidence', 0) > 75:
                prominent_texts.append(t.get('DetectedText', '').strip())
        prominent_texts = prominent_texts[:3]

        # Determine dominant colors if available
        dominant_colors = []
        for color in image_props.get('DominantColors', [])[:2]:
            c_name = color.get('SimplifiedColor', '')
            if c_name and c_name not in dominant_colors:
                dominant_colors.append(c_name.lower())

        # Synthesize primary caption
        main_subject = ""
        if people_labels:
            main_subject = people_labels[0]
            if len(people_labels) > 1 and people_labels[1].lower() != people_labels[0].lower():
                main_subject += f" and {people_labels[1]}"
        elif animal_labels:
            main_subject = f"a {animal_labels[0]}"
            if len(animal_labels) > 1:
                main_subject += f" ({animal_labels[1]})"
        elif object_labels:
            main_subject = f"{object_labels[0]}"
            if len(object_labels) > 1:
                main_subject += f" and {object_labels[1]}"
        else:
            main_subject = top_labels[0] if top_labels else "scene"

        # Determine setting / context
        setting = ""
        if environment_labels:
            setting = f" in a {environment_labels[0].lower()} setting"

        # Activity or state
        activity = ""
        if activity_labels:
            activity = f", engaged in {activity_labels[0].lower()}"

        # Color tone
        color_tone = ""
        if dominant_colors:
            color_tone = f" with dominant {' and '.join(dominant_colors)} tones"

        # Construct fluent caption
        primary_caption = f"A photo showcasing {main_subject}{setting}{activity}{color_tone}."
        
        # Capitalize and clean up
        primary_caption = primary_caption.replace("  ", " ").strip()

        # Construct short caption
        key_elements = []
        for item in [main_subject, environment_labels[0] if environment_labels else None, activity_labels[0] if activity_labels else None]:
            if item:
                key_elements.append(item.replace("a ", "").replace("an ", ""))
        short_caption = " • ".join(key_elements[:3]).capitalize()

        # Detailed description
        text_note = f" Detected text on image: \"{' | '.join(prominent_texts)}\"." if prominent_texts else ""
        all_features = ", ".join(top_labels[:7])
        detailed_description = (
            f"The image prominently features {main_subject}{setting}. "
            f"Visual analysis identified key elements including {all_features}."
            f"{text_note}"
        )

        # Generate hashtags
        hashtags = [f"#{tag.replace(' ', '')}" for tag in top_labels[:8]]
        if prominent_texts:
            hashtags.append("#TextDetected")

        # Format label summary for frontend badges
        labels_summary = [
            {
                "name": l['Name'],
                "confidence": round(l.get('Confidence', 0), 1),
                "categories": [c.get('Name') for c in l.get('Categories', [])]
            }
            for l in sorted_labels[:15]
        ]

        return {
            "primary_caption": primary_caption,
            "short_caption": short_caption,
            "detailed_description": detailed_description,
            "hashtags": hashtags,
            "labels_summary": labels_summary,
            "detected_text": prominent_texts,
            "colors": dominant_colors
        }

    @staticmethod
    def get_mock_caption(filename="image.jpg") -> Dict[str, Any]:
        """Provides realistic mock analysis when testing without AWS credentials."""
        mock_data = {
            "labels": [
                {"Name": "Landscape", "Confidence": 99.1, "Categories": [{"Name": "Nature"}]},
                {"Name": "Mountain", "Confidence": 98.4, "Categories": [{"Name": "Nature"}]},
                {"Name": "Outdoors", "Confidence": 97.8, "Categories": [{"Name": "Environment"}]},
                {"Name": "Sky", "Confidence": 96.5, "Categories": [{"Name": "Nature"}]},
                {"Name": "Sunlight", "Confidence": 91.2, "Categories": [{"Name": "Weather"}]},
                {"Name": "Scenic View", "Confidence": 89.0, "Categories": [{"Name": "Travel"}]},
                {"Name": "Lake", "Confidence": 85.3, "Categories": [{"Name": "Water"}]},
                {"Name": "Forest", "Confidence": 82.7, "Categories": [{"Name": "Plants"}]}
            ],
            "image_properties": {
                "DominantColors": [
                    {"SimplifiedColor": "Blue"},
                    {"SimplifiedColor": "Green"}
                ]
            },
            "text_detections": []
        }
        res = CaptionEngine.generate_captions_from_rekognition(mock_data)
        res["is_demo_mode"] = True
        res["notice"] = "Demo Mode: Configure your AWS credentials in Settings or .env to run live AWS Rekognition queries."
        return res
