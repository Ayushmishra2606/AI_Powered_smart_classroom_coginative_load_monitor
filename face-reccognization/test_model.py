import cv2, sys, numpy, os

size = 4
haar_file = 'haarcascade_frontalface_default.xml'
datasets = 'database'
model_filename = 'face_recognizer.yml'

print('Loading model...')
# Create the LBPH Face Recognizer and load the model
model = cv2.face.LBPHFaceRecognizer_create()
if not os.path.exists(model_filename):
    print(f"Error: Model file '{model_filename}' not found. Please run train_model.py first.")
    sys.exit()

model.read(model_filename)
print('Model loaded. Starting recognition...')

# Load names to identify labels
(names, id) = ({}, 0)
for (subdirs, dirs, files) in os.walk(datasets):
    for subdir in dirs:
        names[id] = subdir
        id += 1

(width, height) = (130, 100)
face_cascade = cv2.CascadeClassifier(haar_file)
webcam = cv2.VideoCapture(0)

print("Press 'q' to quit.")
while True:
    (_, im) = webcam.read()
    if im is None:
        print("Error: Could not read frame from webcam.")
        break
        
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    for (x, y, w, h) in faces:
        cv2.rectangle(im, (x, y), (x + w, y + h), (255, 0, 0), 2)
        face = gray[y:y + h, x:x + w]
        face_resize = cv2.resize(face, (width, height))
        
        # Try to recognize the face
        prediction = model.predict(face_resize)
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0), 3)

        if prediction[1] < 500:
            name = names[prediction[0]]
            confidence = prediction[1]
            cv2.putText(im, '%s - %.0f' % (name, confidence), (x - 10, y - 10),
                        cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0))
        else:
            cv2.putText(im, 'not recognized', (x - 10, y - 10), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0))

    cv2.imshow('OpenCV', im)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
        
webcam.release()
cv2.destroyAllWindows()
