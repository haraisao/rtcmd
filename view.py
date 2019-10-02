import os,sys
import tkinter
from PIL import ImageTk

class ImageView():
    def __init__(self, fname='rtcmd.png'):
        self.fname=fname
        self.update_time=1000
        self.root = tkinter.Tk()
        self.root.geometry("600x400")
        self.root.title("System View")

        self.canvas = tkinter.Canvas(bg="black", width=600, height=400)
        self.canvas.place(x=0, y=0)

        self.image = ImageTk.PhotoImage(file=self.fname)
        self.imgCanvas = self.canvas.create_image(1, 1, image=self.image, anchor=tkinter.NW)

    def reload_image(self):
        self.image = ImageTk.PhotoImage(file=self.fname)
        self.canvas.itemconfig(self.imgCanvas, image=self.image)
        self.root.after(self.update_time, self.reload_image)

    def start(self):
        self.root.after(self.update_time, self.reload_image)
        self.root.mainloop()

if __name__ == '__main__':
    view=ImageView('rtcmd.png')
    view.start()

