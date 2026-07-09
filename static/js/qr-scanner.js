// QR Code Scanner dengan JavaScript
class QRCodeScanner {
    constructor(videoElement, resultCallback) {
        this.videoElement = videoElement;
        this.resultCallback = resultCallback;
        this.stream = null;
        this.scanning = false;
        
        // Check for QR code reader support
        this.supported = 'BarcodeDetector' in window;
    }
    
    async start() {
        if (!this.supported) {
            console.warn('BarcodeDetector API not supported');
            return false;
        }
        
        try {
            // Get camera stream
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });
            
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();
            
            // Start scanning
            this.scanning = true;
            this.scanFrame();
            
            return true;
        } catch (error) {
            console.error('Error accessing camera:', error);
            return false;
        }
    }
    
    async scanFrame() {
        if (!this.scanning) return;
        
        try {
            const barcodeDetector = new BarcodeDetector({ formats: ['qr_code'] });
            const barcodes = await barcodeDetector.detect(this.videoElement);
            
            if (barcodes.length > 0) {
                const qrData = barcodes[0].rawValue;
                this.resultCallback(qrData);
                this.stop();
            }
        } catch (error) {
            console.warn('Error detecting QR:', error);
        }
        
        // Continue scanning
        if (this.scanning) {
            requestAnimationFrame(() => this.scanFrame());
        }
    }
    
    stop() {
        this.scanning = false;
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.videoElement.srcObject = null;
        }
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = QRCodeScanner;
} else {
    window.QRCodeScanner = QRCodeScanner;
}