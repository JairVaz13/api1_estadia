from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
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
import uvicorn

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

# Configuración de MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client.image_database
image_collection = db.images

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

    result = image_collection.insert_one({"url": f"/uploads/{image.filename}"})
    return JSONResponse({"success": True, "imageUrl": f"/uploads/{image.filename}", "id": str(result.inserted_id)})

@app.get("/images")
async def get_images():
    images = image_collection.find()
    image_urls = []
    for img in images:
        if "url" in img:
            image_urls.append({"url": img["url"], "id": str(img["_id"])})
    return JSONResponse({"images": image_urls})

@app.delete("/images/{image_id}")
async def delete_image(image_id: str):
    # Validar el formato del ID
    try:
        object_id = ObjectId(image_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image ID")

    # Buscar la imagen en la base de datos
    image = image_collection.find_one({"_id": object_id})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Eliminar el archivo de la carpeta uploads
    file_path = os.path.join(UPLOAD_DIRECTORY, image["url"].split('/')[-1])
    if os.path.exists(file_path):
        os.remove(file_path)

    # Eliminar la entrada de la base de datos
    image_collection.delete_one({"_id": object_id})

    return JSONResponse({"success": True})

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

def delete_contact(contact_id: str):
    contacts = read_csv_contacts()
    contacts = [c for c in contacts if c["id"] != contact_id]
    write_csv_contacts(contacts)
    return {"detail": "Contact deleted"}

@app.post("/contacts/", response_model=Contact)
async def create_contact_endpoint(contact: ContactCreate):
    return create_contact(contact)

@app.get("/contacts/", response_model=List[Contact])
async def list_contacts():
    return get_contacts()

@app.get("/contacts/{contact_id}", response_model=Contact)
async def get_contact_endpoint(contact_id: str):
    contact = get_contact(contact_id)
    if contact:
        return contact
    raise HTTPException(status_code=404, detail="Contact not found")

@app.put("/contacts/{contact_id}", response_model=Contact)
async def update_contact_endpoint(contact_id: str, contact: ContactUpdate):
    updated_contact = update_contact(contact_id, contact)
    if updated_contact:
        return updated_contact
    raise HTTPException(status_code=404, detail="Contact not found")

@app.delete("/contacts/{contact_id}")
async def delete_contact_endpoint(contact_id: str):
    delete_contact(contact_id)
    return {"detail": "Contact deleted"}

# Directorio para videos
VIDEO_DIRECTORY = "./static/videos"
os.makedirs(VIDEO_DIRECTORY, exist_ok=True)

@app.post("/videos/upload")
async def upload_video(video: UploadFile = File(...)):
    file_location = f"{VIDEO_DIRECTORY}/{video.filename}"
    with open(file_location, "wb") as file:
        shutil.copyfileobj(video.file, file)
    return {"info": f"file '{video.filename}' saved at '{file_location}'"}

@app.get("/videos/")
async def list_videos():
    videos = [f for f in os.listdir(VIDEO_DIRECTORY) if os.path.isfile(os.path.join(VIDEO_DIRECTORY, f))]
    return {"videos": videos}

@app.delete("/videos/{filename}")
async def delete_video(filename: str):
    file_path = os.path.join(VIDEO_DIRECTORY, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"detail": "Video deleted"}
    raise HTTPException(status_code=404, detail="Video not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
