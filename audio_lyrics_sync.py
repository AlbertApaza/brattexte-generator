import shutil
from threading import Thread
from tracemalloc import BaseFilter
import pygame
import time
import os
import json
from tkinter import Tk, Button, filedialog, Canvas, Label, Listbox, Entry, messagebox, Frame, Menu
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from PyQt5.QtWidgets import QMenu, QAction
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import subprocess
import tempfile

class AudioLyricsSync:

####### INICIO DE INTERFAZ #######

    def __init__(self, root):
        self.root = root
        self.root.title("Sync Audio & Lyrics")
        
        file_frame = Frame(root)
        file_frame.pack(pady=5)

        # BOTONES
        # BOTON- AUDIO
        self.load_audio_btn = Button(file_frame, text="Cargar Audio", command=self.load_audio)
        self.load_audio_btn.pack(side="left", padx=5)
        

        self.load_json_btn = Button(file_frame, text="Cargar Letras (JSON)", command=self.load_fragments_json, bg="#4b89dc", fg="white")
        self.load_json_btn.pack(side="left", padx=5)
        
        self.save_all_btn = Button(file_frame, text="Guardar Letras (JSON)", command=self.save_all_fragments, bg="green", fg="white")
        self.save_all_btn.pack(side="left", padx=5)

        control_frame = Frame(root)
        control_frame.pack(pady=5)
        
        self.play_btn = Button(control_frame, text="▶ Reproducir", command=self.play_audio)
        self.play_btn.pack(side="left", padx=2)

        self.pause_btn = Button(control_frame, text="⏸ Pausar", command=self.pause_audio)
        self.pause_btn.pack(side="left", padx=2)

        self.rewind_btn = Button(control_frame, text="⏪ Retroceder 5s", command=lambda: self.change_time(-5))
        self.rewind_btn.pack(side="left", padx=2)

        self.forward_btn = Button(control_frame, text="⏩ Adelantar 5s", command=lambda: self.change_time(5))
        self.forward_btn.pack(side="left", padx=2)


        self.toggle_center_btn = Button(root, text="Alternar Centrado", command=self.toggle_auto_center)
        self.toggle_center_btn.pack()

        self.auto_center = True

        self.mark_fragment_btn = Button(root, text="Marcar Fragmento 🚩", command=self.mark_fragment,
                                        bg="#e74c3c", fg="yellow", font=("Helvetica", 10, "bold"))
        self.mark_fragment_btn.pack(pady=5)

        self.fragment_listbox = Listbox(root, height=10, width=50)
        self.fragment_listbox.pack(pady=5)
        self.fragment_listbox.bind("<<ListboxSelect>>", self.select_fragment)  # Al hacer click derecho en un fragmento

        self.lyrics_entry = Entry(root, width=50)
        self.lyrics_entry.pack(pady=5)

        self.save_lyrics_btn = Button(root, text="Guardar Letra", command=self.save_lyrics)
        self.save_lyrics_btn.pack(pady=5)

        self.generate_video_btn = Button(root, text="Generar Video", command=self.generate_video, 
                                      bg="#e74c3c", fg="white", font=("Helvetica", 10, "bold"))
        self.generate_video_btn.pack(pady=5)

        self.duration_label = Label(root, text="Duración: 0:00", font=("Helvetica", 12))
        self.duration_label.pack(pady=2)

        self.current_time_label = Label(root, text="Tiempo: 0:00", font=("Helvetica", 12))
        self.current_time_label.pack(pady=2)
        
        self.song_info_label = Label(root, text="Canción: No seleccionada", font=("Helvetica", 10))
        self.song_info_label.pack(pady=2)

        self.canvas = Canvas(root, height=20, width=400, bg="lightgray")
        self.canvas.pack(pady=5)
        self.canvas.bind("<Button-1>", self.jump_to_time_from_bar)

        pygame.mixer.init()
        self.audio_path = None
        self.song_length = 0
        self.current_position = 0
        self.is_playing = False
        self.start_time = None

        self.fragments = []
        self.selected_fragment_index = None
        self.song_name = ""

        self.fragment_listbox.bind("<Button-3>", self.show_context_menu)

        self.context_menu = Menu(root, tearoff=0)
        self.context_menu.add_command(label="Eliminar Fragmento", command=self.delete_selected_fragment)
        self.context_menu.add_command(label="Agregar Imagen", command=self.generate_image_from_text)

        # para guardar al cerrar la ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.loaded_json_path = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)



####### INICIO DE FUNCIONES #######

    #Funcion para generar todo directamente del video
    def generate_video(self):
        """Generar un video con las imágenes de los fragmentos y el audio sincronizado"""
        if not self.audio_path:
            messagebox.showwarning("Advertencia", "Primero debes cargar un archivo de audio.")
            return
            
        if not self.fragments:
            messagebox.showwarning("Advertencia", "No hay fragmentos para generar el video.")
            return
            
        try:
            temp_dir = tempfile.mkdtemp()
            
            for i, (time_stamp, text) in enumerate(self.fragments):
                img_size = 400
                img = Image.new('RGB', (img_size, img_size), color='white')
                draw = ImageDraw.Draw(img)

                try:
                    font = ImageFont.truetype("arial.ttf", 50)
                except IOError:
                    font = ImageFont.load_default()

                wrapped_text = textwrap.fill(text, width=15)
                text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # centrar el texto en la imagen
                text_x = (img_size - text_width) // 2
                text_y = (img_size - text_height) // 2

                draw.text((text_x, text_y), wrapped_text, fill="black", font=font)

                img = img.filter(ImageFilter.GaussianBlur(radius=1))

                # Guardar la imagen en baja calidad
                image_path = os.path.join(temp_dir, f"fragmento_{i:04d}.png")
                img.save(image_path, quality=50)
                
            ffmpeg_input_file = os.path.join(temp_dir, "input.txt")
            with open(ffmpeg_input_file, 'w') as f:
                prev_time = 0
                for i, (time_stamp, _) in enumerate(self.fragments):
                    duration = time_stamp - prev_time if i > 0 else time_stamp
                    if i < len(self.fragments) - 1:
                        next_time = self.fragments[i+1][0]
                        duration = next_time - time_stamp
                    else:
                        duration = self.song_length - time_stamp
                        
                    f.write(f"file '{os.path.join(temp_dir, f'fragmento_{i:04d}.png')}'\n")
                    f.write(f"duration {duration}\n")
                    prev_time = time_stamp
                
                f.write(f"file '{os.path.join(temp_dir, f'fragmento_{len(self.fragments)-1:04d}.png')}'\n")
                f.write(f"duration 0.1\n")
            
            # Preguntar dónde guardar el video
            video_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("Archivos MP4", "*.mp4"), ("Todos los archivos", "*.*")],
                initialfile=f"{os.path.splitext(self.song_name)[0]}_video"
            )
            
            if not video_path:
                return
                
            # Comando para generar el video con FFmpeg
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", ffmpeg_input_file,
                "-i", self.audio_path,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-c:a", "aac",
                video_path
            ]
            
            # Ejecutar FFmpeg
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                messagebox.showinfo("Éxito", f"Video generado correctamente en {video_path}")
            else:
                error_message = stderr.decode()
                if "ffmpeg: command not found" in error_message or "No such file or directory" in error_message:
                    messagebox.showerror("Error", "FFmpeg no está instalado o no se encuentra en el PATH. Por favor, instala FFmpeg para usar esta función.")
                else:
                    messagebox.showerror("Error", f"Error al generar el video: {error_message}")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al generar el video: {str(e)}")
            
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass


    # Funcion para generar por cada fragmento
    def generate_image_from_text(self):
        selected_index = self.fragment_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("Advertencia", "Seleccione un fragmento para generar la imagen.")
            return

        index = selected_index[0]
        time_stamp, text = self.fragments[index]

        img_size = 400
        img = Image.new('RGB', (img_size, img_size), color='white')
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 50)
        except IOError:
            font = ImageFont.load_default()

        wrapped_text = textwrap.fill(text, width=15)
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        text_x = (img_size - text_width) // 2
        text_y = (img_size - text_height) // 2

        draw.text((text_x, text_y), wrapped_text, fill="black", font=font)

        img = img.filter(ImageFilter.GaussianBlur(radius=1))

        image_path = f"fragmento_{index + 1}.png"
        img.save(image_path, quality=50)

        messagebox.showinfo("Imagen Creada", f"La imagen se ha guardado como {image_path}")


    # Funcion para preguntar si desea guardar la letra antes de perder la letra creada
    def on_closing(self):
        if self.fragments:
            respuesta = messagebox.askyesnocancel(
                "Guardar Cambios", 
                "¿Deseas guardar los cambios antes de salir?"
            )

            if respuesta is None: # NO GUARDAR
                return
            
            if respuesta:  # SI GUARDAR
                self.save_all_fragments() 

        self.root.destroy()

    # BORRAR FRAGMENTO CON CLICK DERECHO EN CADA FRAGMENTO
    def delete_selected_fragment(self):
        try:
            selected_index = self.fragment_listbox.curselection()
            if selected_index:
                index = selected_index[0]
                del self.fragments[index]
                self.fragment_listbox.delete(index)
                self.selected_fragment_index = None
        except Exception as e:
            print("Error al eliminar fragmento:", e)

    def show_context_menu(self, event):
        try:
            self.fragment_listbox.selection_clear(0, "end")
            self.fragment_listbox.selection_set(self.fragment_listbox.nearest(event.y))
            self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print("Error al mostrar menú contextual:", e)

    def mostrar_menu_contextual(self, pos):
        menu = QMenu(self.lista_marcadores)
        eliminar_action = QAction("Eliminar", self.lista_marcadores)
        eliminar_action.triggered.connect(self.eliminar_marcador_seleccionado)
        menu.addAction(eliminar_action)
        
        menu.exec_(self.lista_marcadores.mapToGlobal(pos))

    def eliminar_marcador_seleccionado(self):
        item = self.lista_marcadores.currentItem()
        if item:
            self.lista_marcadores.takeItem(self.lista_marcadores.row(item))

    def load_audio(self):
        """Cargar un archivo de audio y mostrar su duración"""
        self.audio_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3;*.wav")])
        if self.audio_path:
            pygame.mixer.music.load(self.audio_path)
            self.song_length = self.get_audio_duration(self.audio_path)
            minutes, seconds = divmod(int(self.song_length), 60)
            self.duration_label.config(text=f"Duración: {minutes}:{seconds:02d}")
            
            self.song_name = os.path.basename(self.audio_path)
            self.root.title(f"Sync Audio & Lyrics - {self.song_name}")
            self.song_info_label.config(text=f"Canción: {self.song_name}")
            
            self.fragments = []
            self.update_fragment_listbox()

    def get_audio_duration(self, file_path):
        """Obtener la duración del audio en segundos usando mutagen"""
        if file_path.endswith(".mp3"):
            audio = MP3(file_path)
        elif file_path.endswith(".wav"):
            audio = WAVE(file_path)
        else:
            return 0
        return audio.info.length

    def play_audio(self):
        """Reproducir audio desde la posición actual y actualizar la selección de fragmentos"""
        if not self.audio_path:
            messagebox.showwarning("Advertencia", "Primero debes cargar un archivo de audio.")
            return

        pygame.mixer.music.load(self.audio_path)
        pygame.mixer.music.play(start=self.current_position)
        
        self.is_playing = True
        self.start_time = time.time() - self.current_position

        self.update_progress_bar()

        thread = Thread(target=self.update_fragment_selection, daemon=True)
        thread.start()

    def update_fragment_selection(self):
        """Actualizar la selección en la lista de fragmentos según el tiempo de reproducción"""
        last_selected = -1
        user_interacting = False

        def on_mousewheel(event):
            """Detecta cuando el usuario usa la rueda del mouse"""
            nonlocal user_interacting
            user_interacting = True
            self.fragment_listbox.after(2000, lambda: setattr(self, "user_interacting", False))

        self.fragment_listbox.bind("<MouseWheel>", on_mousewheel)

        while self.is_playing:
            current_time = self.get_audio_position()
            new_selected = None

            for i, (time_stamp, _) in enumerate(self.fragments):
                if current_time >= time_stamp:
                    new_selected = i
                else:
                    break

            if new_selected is not None and new_selected != last_selected:
                self.fragment_listbox.selection_clear(0, "end")
                self.fragment_listbox.selection_set(new_selected)
                self.fragment_listbox.activate(new_selected)

                if self.auto_center and not user_interacting:
                    list_size = self.fragment_listbox.size()
                    half_visible = min(4, list_size // 2)
                    target_index = max(0, new_selected - half_visible)
                    self.fragment_listbox.yview(target_index)

                last_selected = new_selected

            time.sleep(0.3)

    def toggle_auto_center(self):
        """Alternar entre centrado automático y manual"""
        self.auto_center = not self.auto_center
        mode = "Activado" if self.auto_center else "Desactivado"
        print(f"Centrado automático: {mode}")


    def get_audio_position(self):
        """Retorna el tiempo actual de reproducción en segundos"""
        if pygame.mixer.music.get_busy():
            return time.time() - self.start_time
        return self.current_position
    
    def pause_audio(self):
        """Pausar o reanudar el audio"""
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True






    def change_time(self, seconds):
        """Adelantar o retroceder el audio"""
        self.current_position += seconds
        self.current_position = max(0, min(self.current_position, self.song_length))
        self.play_audio()

    def update_progress_bar(self):
        """Actualizar la barra mientras se reproduce el audio"""
        if pygame.mixer.music.get_busy():
            self.current_position = time.time() - self.start_time
            minutes, seconds = divmod(int(self.current_position), 60)
            self.current_time_label.config(text=f"Tiempo: {minutes}:{seconds:02d}")

            self.canvas.delete("progress")
            bar_width = int((self.current_position / self.song_length) * 400)
            self.canvas.create_rectangle(0, 0, bar_width, 20, fill="blue", tags="progress")

            self.root.after(100, self.update_progress_bar)

    def mark_fragment(self):
        """Marcar el tiempo actual de la canción para sincronizar con una línea de la letra"""
        if self.is_playing:
            fragment_time = round(self.current_position, 2)
            self.fragments.append((fragment_time, "Escribe la letra aquí"))

            self.fragments.sort(key=lambda x: x[0])

            self.update_fragment_listbox()

    def update_fragment_listbox(self):
        """Actualizar la lista de fragmentos"""
        self.fragment_listbox.delete(0, "end")
        for time_stamp, lyric in self.fragments:
            minutes, seconds = divmod(int(time_stamp), 60)
            formatted_time = f"{minutes}:{seconds:02d}"
            self.fragment_listbox.insert("end", f"{formatted_time} - {lyric}")

    def select_fragment(self, event):
        """Seleccionar un fragmento y mostrarlo en el campo de edición"""
        selected_index = self.fragment_listbox.curselection()
        if selected_index:
            self.selected_fragment_index = selected_index[0]
            time_stamp, lyric = self.fragments[self.selected_fragment_index]
            self.lyrics_entry.delete(0, "end")
            self.lyrics_entry.insert(0, lyric)

            self.current_position = time_stamp
            self.play_audio()

    def save_lyrics(self):
        """Guardar la letra en el fragmento seleccionado"""
        if self.selected_fragment_index is not None:
            new_lyric = self.lyrics_entry.get()
            time_stamp, _ = self.fragments[self.selected_fragment_index]
            self.fragments[self.selected_fragment_index] = (time_stamp, new_lyric)

            self.update_fragment_listbox()

    def jump_to_time_from_bar(self, event):
        """Saltar a un segundo específico al hacer clic en la barra"""
        self.current_position = (event.x / 400) * self.song_length
        self.play_audio()

    def save_all_fragments(self):
        """Guardar todos los fragmentos sincronizados con la canción actual"""
        if not self.audio_path or not self.fragments:
            messagebox.showwarning("Advertencia", "No hay canción cargada o fragmentos para guardar.")
            return
        
        data = {
            "song_name": self.song_name,
            "audio_path": self.audio_path,
            "fragments": self.fragments
        }
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")],
            initialfile=f"{os.path.splitext(self.song_name)[0]}_lyrics"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Éxito", f"Fragmentos guardados correctamente en {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar los fragmentos: {str(e)}")
    

    # FUNCION PARA CARGAR EL JSON CON LA LETRA GUARDAD ANTERIORMENTE (SE UTILIZA TUPLAS :d)
    def load_fragments_json(self):
        """Cargar fragmentos guardados desde un archivo JSON"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not all(key in data for key in ["song_name", "audio_path", "fragments"]):
                messagebox.showerror("Error", "El archivo JSON no tiene el formato correcto.")
                return
                
            self.song_name = data["song_name"]
            audio_path = data["audio_path"]
            
            if os.path.exists(audio_path):
                self.audio_path = audio_path
            else:
                messagebox.showinfo(
                    "Archivo de audio no encontrado", 
                    f"El archivo de audio original '{os.path.basename(audio_path)}' no se encuentra en la ubicación guardada. Por favor, selecciónelo."
                )
                new_audio_path = filedialog.askopenfilename(
                    filetypes=[("Audio Files", "*.mp3;*.wav")],
                    initialfile=os.path.basename(audio_path)
                )
                
                if new_audio_path:
                    self.audio_path = new_audio_path
                else:
                    messagebox.showwarning("Advertencia", "No se seleccionó archivo de audio. Las letras se cargarán sin audio asociado.")
            
            self.fragments = [tuple(fragment) for fragment in data["fragments"]]
            
            self.update_fragment_listbox()
            self.root.title(f"Sync Audio & Lyrics - {self.song_name}")
            self.song_info_label.config(text=f"Canción: {self.song_name}")
            
            if self.audio_path and os.path.exists(self.audio_path):
                pygame.mixer.music.load(self.audio_path)
                self.song_length = self.get_audio_duration(self.audio_path)
                minutes, seconds = divmod(int(self.song_length), 60)
                self.duration_label.config(text=f"Duración: {minutes}:{seconds:02d}")
                
            messagebox.showinfo("Éxito", f"Se han cargado {len(self.fragments)} fragmentos para la canción '{self.song_name}'")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el archivo JSON: {str(e)}")