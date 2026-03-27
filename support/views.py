from django.shortcuts import render


def chat_page(request):
    return render(request, "chat.html")


from .forms import PDFUploadForm
from .models import PDFUpload
from django.http import HttpResponseRedirect

def pdf_upload(request):
    if request.method == "POST":
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return render(request, "pdf_upload.html", {"form": PDFUploadForm(), "success": True})
    else:
        form = PDFUploadForm()
    return render(request, "pdf_upload.html", {"form": form})
