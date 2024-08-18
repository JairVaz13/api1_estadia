from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import List
import csv
import io
import shutil
import os
import uuid
from pathlib import Path
from pymongo import MongoClient
from bson import ObjectId

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todas las fuentes (para desarrollo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivo CSV para almacenar eventos
CSV_FILE_PATH = "eventos.csv"

class Evento(BaseModel):
    titulo: str
    descripcion: str
    ubicacion: str
    fecha: str
    hora: str

class EventoDB(Evento):
    id: int

def read_csv():
    eventos = []
    try:
        with open(CSV_FILE_PATH, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                eventos.append(EventoDB(
                    id=int(row['ID']),
                    titulo=row['Titulo'],
                    descripcion=row['Descripcion'],
                    ubicacion=row['Ubicacion'],
                    fecha=row['Fecha'],
                    hora=row['Hora']
                ))
    except FileNotFoundError:
        pass
    return eventos

def write_csv(eventos: List[EventoDB]):
    with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ID', 'Titulo', 'Descripcion', 'Ubicacion', 'Fecha', 'Hora']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for evento in eventos:
            writer.writerow({
                'ID': evento.id,
                'Titulo': evento.titulo,
                'Descripcion': evento.descripcion,
                'Ubicacion': evento.ubicacion,
                'Fecha': evento.fecha,
                'Hora': evento.hora
            })

@app.get("/eventos", response_model=List[EventoDB])
async def obtener_eventos(skip: int = 0, limit: int = Query(default=2, lte=50)):
    eventos = read_csv()
    eventos_ordenados = sorted(eventos, key=lambda x: x.fecha)  # Ordenar por fecha ascendente
    return eventos_ordenados[skip:skip + limit]

@app.post("/eventos", response_model=EventoDB)
async def crear_evento(evento: Evento):
    eventos = read_csv()
    nuevo_id = max(e.id for e in eventos) + 1 if eventos else 1
    evento_db = EventoDB(id=nuevo_id, **evento.dict())
    eventos.append(evento_db)
    write_csv(eventos)
    return evento_db

@app.put("/eventos/{evento_id}", response_model=EventoDB)
async def actualizar_evento(evento_id: int, evento: Evento):
    eventos = read_csv()
    for i, e in enumerate(eventos):
        if e.id == evento_id:
            eventos[i] = EventoDB(id=evento_id, **evento.dict())
            write_csv(eventos)
            return eventos[i]
    raise HTTPException(status_code=404, detail="Evento no encontrado")

@app.delete("/eventos/{evento_id}")
async def eliminar_evento(evento_id: int):
    eventos = read_csv()
    eventos = [e for e in eventos if e.id != evento_id]
    write_csv(eventos)
    return {"detail": "Evento eliminado correctamente"}

@app.get("/exportar_csv")
async def exportar_eventos_csv():
    eventos = read_csv()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Titulo", "Descripcion", "Ubicacion", "Fecha", "Hora"])  # Escribir encabezados
    for evento in eventos:
        writer.writerow([
            evento.id,
            evento.titulo,
            evento.descripcion,
            evento.ubicacion,
            evento.fecha,
            evento.hora
        ])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=eventos.csv"})


# Archivo CSV para almacenar contactos
CSV_FILE = Path("contacts.csv")

# Initialize CSV file
def init_csv():
    if not CSV_FILE.exists():
        with open(CSV_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["id", "name", "email", "phone", "message"])

# Read data from CSV
def read_csv_contacts():
    with open(CSV_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        return list(reader)

# Write data to CSV
def write_csv_contacts(rows):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=["id", "name", "email", "phone", "message"])
        writer.writeheader()
        writer.writerows(rows)

init_csv()

# Models
class Contact(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: str
    message: str

class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    message: str

class ContactUpdate(BaseModel):
    name: str = None
    email: EmailStr = None
    phone: str = None
    message: str = None

# CRUD operations for contacts
def create_contact(contact: ContactCreate) -> Contact:
    contacts = read_csv_contacts()
    new_contact = contact.dict()
    new_contact["id"] = str(uuid.uuid4())
    contacts.append(new_contact)
    write_csv_contacts(contacts)
    return Contact(**new_contact)

def get_contact(contact_id: str) -> Contact:
    contacts = read_csv_contacts()
    for contact in contacts:
        if contact["id"] == contact_id:
            return Contact(**contact)
    return None

def get_contacts() -> List[Contact]:
    contacts = read_csv_contacts()
    return [Contact(**contact) for contact in contacts]

def update_contact(contact_id: str, contact: ContactUpdate) -> Contact:
    contacts = read_csv_contacts()
    for idx, existing_contact in enumerate(contacts):
        if existing_contact["id"] == contact_id:
            updated_data = contact.dict(exclude_unset=True)
            contacts[idx] = {**existing_contact, **updated_data}
            write_csv_contacts(contacts)
            return Contact(**contacts[idx])
    return None

def delete_contact(contact_id: str) -> bool:
    contacts = read_csv_contacts()
    new_contacts = [contact for contact in contacts if contact["id"] != contact_id]
    if len(new_contacts) != len(contacts):
        write_csv_contacts(new_contacts)
        return True
    return False

# Routes for contacts
@app.post("/contacts/", response_model=Contact)
def create_contact_route(contact: ContactCreate):
    return create_contact(contact)

@app.get("/contacts/", response_model=List[Contact])
def read_contacts_route():
    return get_contacts()

@app.get("/contacts/{contact_id}", response_model=Contact)
def read_contact_route(contact_id: str):
    contact = get_contact(contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@app.put("/contacts/{contact_id}", response_model=Contact)
def update_contact_route(contact_id: str, contact: ContactUpdate):
    updated_contact = update_contact(contact_id, contact)
    if updated_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return updated_contact

@app.delete("/contacts/{contact_id}")
def delete_contact_route(contact_id: str):
    success = delete_contact(contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"detail": "Contact deleted"}


from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from typing import List



UPLOAD_DIR = 'static/videos'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Video model
class Video(BaseModel):
    id: int
    title: str
    filename: str

# In-memory "database"
videos = []

@app.post("/videos/", response_model=Video)
async def create_video(title: str = Form(...), video: UploadFile = File(...)):
    video_id = len(videos) + 1
    file_path = os.path.join(UPLOAD_DIR, video.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await video.read())
    
    new_video = Video(id=video_id, title=title, filename=video.filename)
    videos.append(new_video)
    return new_video

@app.get("/videos/", response_model=List[Video])
async def get_videos():
    return videos

@app.get("/videos/{video_id}", response_class=FileResponse)
async def get_video(video_id: int):
    video = next((v for v in videos if v.id == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return os.path.join(UPLOAD_DIR, video.filename)

@app.put("/videos/{video_id}", response_model=Video)
async def update_video(video_id: int, title: str = Form(...), video: UploadFile = File(None)):
    video_to_update = next((v for v in videos if v.id == video_id), None)
    if not video_to_update:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video:
        file_path = os.path.join(UPLOAD_DIR, video.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await video.read())
        video_to_update.filename = video.filename
    
    video_to_update.title = title
    return video_to_update

@app.delete("/videos/{video_id}", response_model=Video)
async def delete_video(video_id: int):
    global videos
    video_to_delete = next((v for v in videos if v.id == video_id), None)
    if not video_to_delete:
        raise HTTPException(status_code=404, detail="Video not found")
    
    file_path = os.path.join(UPLOAD_DIR, video_to_delete.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    videos = [v for v in videos if v.id != video_id]
    return video_to_delete


from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil


# Directorio para subir imágenes
UPLOAD_DIRECTORY = "./uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Montar el directorio de uploads para servir archivos estáticos
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIRECTORY), name="uploads")

@app.post("/upload")
async def upload_image(image: UploadFile = File(...)):
    file_location = f"{UPLOAD_DIRECTORY}/{image.filename}"
    with open(file_location, "wb") as file:
        shutil.copyfileobj(image.file, file)

    return JSONResponse({"success": True, "imageUrl": f"/uploads/{image.filename}"})

@app.get("/images")
async def get_images():
    # Obtener una lista de los archivos en el directorio de uploads
    image_urls = [{"url": f"/uploads/{filename}"} for filename in os.listdir(UPLOAD_DIRECTORY)]
    return JSONResponse({"images": image_urls})

@app.delete("/images/{image_name}")
async def delete_image(image_name: str):
    file_path = os.path.join(UPLOAD_DIRECTORY, image_name)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        return JSONResponse({"success": True})
    else:
        raise HTTPException(status_code=404, detail="Image not found")
