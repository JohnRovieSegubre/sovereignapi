’M// Load environment (try project .env first)
const fs = require('fs');
const path = require('path');
const os = require('os');
const projectEnv = path.join(__dirname, '.env');
if (fs.existsSync(projectEnv)) {
	try {
		require('dotenv').config({ path: projectEnv });
	} catch (e) {
		// ignore
	}
} else {
	try {
		require('dotenv').config();
	} catch (e) { }
}

// --- dependencies (CommonJS) ---
const express = require('express');
const multer = require('multer');
const { PDFDocument } = require('pdf-lib');
const sharp = require('sharp'); // ADD THIS LINE
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY || 'sk_test_replace_with_real_key');

// --- app setup ---
const app = express();
const PORT = 3000;

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// storage and files under this server folder (adjust if you prefer file-upload-app root)
const uploadsDir = path.join(__dirname, 'secure_prints');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir);
const PRINT_CODES_FILE = path.join(__dirname, 'print_codes.json');

// pricing from env
const pricing = {
	bw: parseInt(process.env.PRICE_PER_PAGE_BW || '25', 10),
	color: parseInt(process.env.PRICE_PER_PAGE_COLOR || '50', 10),
	legalMultiplier: parseFloat(process.env.PRICE_MULTIPLIER_LEGAL || '1.25'),
	duplexDiscount: parseFloat(process.env.PRICE_DISCOUNT_DUPLEX || '0.95'),
};

// multer memory storage
const storage = multer.memoryStorage();
const upload = multer({ storage });

// helper read/write mapping
function readCodes() {
	try {
		if (fs.existsSync(PRINT_CODES_FILE)) {
			return JSON.parse(fs.readFileSync(PRINT_CODES_FILE, 'utf8') || '{}');
		}
	} catch (e) {
		console.error('Failed to read print codes file:', e);
	}
	return {};
}
function writeCodes(codes) {
	fs.writeFileSync(PRINT_CODES_FILE, JSON.stringify(codes, null, 2), 'utf8');
}

// Helper: check if file is an image
function isImageFile(mimetype) {
	return ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'].includes(mimetype);
}

// Helper: convert image buffer to single-page PDF buffer
async function convertImageToPdf(imageBuffer) {
	// Convert image to PNG buffer (ensures compatibility)
	const pngBuffer = await sharp(imageBuffer).png().toBuffer();
	const metadata = await sharp(imageBuffer).metadata();
	const width = metadata.width || 612;
	const height = metadata.height || 792;

	// Scale to fit on letter page with margins
	const maxWidth = 580;
	const maxHeight = 760;
	const scale = Math.min(maxWidth / width, maxHeight / height, 1);
	const scaledWidth = Math.round(width * scale);
	const scaledHeight = Math.round(height * scale);

	// Create PDF with image
	const pdfDoc = await PDFDocument.create();
	const page = pdfDoc.addPage([612, 792]);
	const pngImage = await pdfDoc.embedPng(pngBuffer);
	const x = (612 - scaledWidth) / 2;
	const y = (792 - scaledHeight) / 2;
	page.drawImage(pngImage, { x, y, width: scaledWidth, height: scaledHeight });

	return await pdfDoc.save();
}

// --- routes ---
// GET /config -> publishable key + pricing for kiosk
app.get('/config', (req, res) => {
	res.json({
		publishableKey: process.env.STRIPE_PUBLISHABLE_KEY || null,
		pricing: {
			bw: pricing.bw,
			color: pricing.color,
			legalMultiplier: pricing.legalMultiplier,
			duplexDiscount: pricing.duplexDiscount,
		},
	});
});

// POST /upload -> store file, count pages, return printCode & numPages (no payment)
// Replace the existing app.post('/upload', ...) with this:
app.post('/upload', upload.single('file'), async (req, res) => {
	if (!req.file) return res.status(400).send('No file uploaded.');

	try {
		let pdfBuffer;
		let numPages;
		let isImage = false;
		const mimetype = req.file.mimetype || '';

		if (mimetype === 'application/pdf') {
			// It's a PDF â€” parse it directly
			pdfBuffer = req.file.buffer;
			const pdfDoc = await PDFDocument.load(pdfBuffer);
			numPages = pdfDoc.getPageCount();
		} else if (isImageFile(mimetype)) {
			// It's an image â€” convert to single-page PDF
			isImage = true;
			pdfBuffer = Buffer.from(await convertImageToPdf(req.file.buffer));
			numPages = 1;
		} else {
			return res.status(400).json({ error: 'Unsupported file type. Please upload a PDF or image.' });
		}

		const printCode = Math.floor(100000 + Math.random() * 900000).toString();
		const uniqueFilename = `${Date.now()}-${printCode}.pdf`;
		const filePath = path.join(uploadsDir, uniqueFilename);
		fs.writeFileSync(filePath, pdfBuffer);

		const codes = readCodes();
		codes[printCode] = { filename: uniqueFilename, numPages, isImage };
		writeCodes(codes);

		const basePrice = isImage ? pricing.color : pricing.bw;
		res.json({ printCode, numPages, priceQuote: numPages * basePrice, isImage });
	} catch (err) {
		console.error('Error processing upload:', err);
		res.status(500).json({ error: 'Failed to process file. Is it a valid PDF or image?' });
	}
});

// POST /get-job-details -> kiosk fetches file metadata for code
app.post('/get-job-details', (req, res) => {
	const { printCode } = req.body || {};
	if (!printCode) return res.status(400).json({ error: 'Missing printCode' });
	const codes = readCodes();
	const job = codes[printCode];
	if (!job) return res.status(404).json({ error: 'Invalid Print Code.' });
	res.json({ filename: job.filename, numPages: job.numPages });
});

// POST /create-payment-intent -> create PaymentIntent on kiosk with options
app.post('/create-payment-intent', async (req, res) => {
	const { printCode, copies = 1, isColor = false, paperSize = 'letter', isDuplex = false } = req.body || {};
	if (!printCode) return res.status(400).json({ error: 'Missing printCode' });

	const codes = readCodes();
	const job = codes[printCode];
	if (!job) return res.status(404).json({ error: 'Invalid Print Code.' });

	// compute price
	let pagePrice = isColor ? pricing.color : pricing.bw;
	let pricePerCopy = job.numPages * pagePrice;
	if (paperSize === 'legal') pricePerCopy *= pricing.legalMultiplier;
	if (isDuplex) pricePerCopy *= pricing.duplexDiscount;
	// Enforce Stripe minimum of 50 cents CAD
	const calculatedAmount = Math.round(pricePerCopy * copies);
	const finalAmountInCents = Math.max(calculatedAmount, 50);

	try {
		const paymentIntent = await stripe.paymentIntents.create({
			amount: finalAmountInCents,
			currency: 'cad',
			automatic_payment_methods: { enabled: true },
			metadata: {
				printCode,
				copies: String(copies),
				isColor: String(isColor),
				paperSize,
				isDuplex: String(isDuplex),
			},
		});

		job.paymentIntentId = paymentIntent.id;
		writeCodes(codes);

		res.json({ clientSecret: paymentIntent.client_secret, finalAmount: finalAmountInCents });
	} catch (err) {
		console.error('Error creating PaymentIntent:', err);
		res.status(500).json({ error: 'Could not create payment intent.' });
	}
});

// POST /print -> verify payment succeeded, print and cleanup
app.post('/print', async (req, res) => {
	const { printCode } = req.body || {};
	if (!printCode) return res.status(400).json({ error: 'Missing printCode' });

	const codes = readCodes();
	const job = codes[printCode];
	if (!job || !job.paymentIntentId) return res.status(400).json({ error: 'Payment has not been initiated for this job.' });

	const filePath = path.join(uploadsDir, job.filename);
	if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found.' });

	try {
		const paymentIntent = await stripe.paymentIntents.retrieve(job.paymentIntentId);
		if (paymentIntent.status !== 'succeeded') {
			return res.status(400).json({ error: 'Payment not successful.' });
		}

		const { copies = '1', isColor = 'true', paperSize = 'letter', isDuplex = 'false' } = paymentIntent.metadata || {};

		const printOptions = {
			copies: parseInt(copies, 10) || 1,
			paperSize: paperSize === 'legal' ? 'Legal' : 'Letter',
			duplex: isDuplex === 'true' ? 'DuplexNoTumble' : undefined,
			options: {
				color: isColor === 'true' ? 'color' : 'monochrome',
			},
		};

		// --- ARCHITECTURE V2 CHANGE: IP PRINTING SIMULATION ---
		// Instead of local driver (pdf-to-printer), we stream to the cabinet printer IP.

		const PRINTER_IP = process.env.PRINTER_IP || '192.168.1.50';
		const PRINTER_PORT = 9100; // Standard RAW printing port

		console.log(`[Architecture V2] Connecting to Printer at ${PRINTER_IP}:${PRINTER_PORT}...`);
		console.log(`[Architecture V2] Streaming ${job.numPages} page(s) job: ${job.filename}`);

		// SIMULATION: In production, we would use 'net' module to open a socket.
		// const client = new net.Socket();
		// client.connect(PRINTER_PORT, PRINTER_IP, () => { client.write(fs.readFileSync(filePath)); });

		await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate network latency
		console.log(`[Architecture V2] Print job sent successfully!`);

		try { fs.unlinkSync(filePath); } catch (e) { console.warn('Could not delete file:', e); }
		delete codes[printCode];
		writeCodes(codes);

		res.json({ success: true, message: "Sent to IP Printer" });
	} catch (err) {
		console.error('Printing error:', err);
		res.status(500).json({ error: 'Failed to send to printer.' });
	}
});

function getLocalIP() {
	const interfaces = os.networkInterfaces();
	for (const name of Object.keys(interfaces)) {
		for (const iface of interfaces[name]) {
			if (iface.family === 'IPv4' && !iface.internal) {
				return iface.address;
			}
		}
	}
	return 'localhost';
}

app.listen(PORT, '0.0.0.0', () => {
	const localIP = getLocalIP();
	console.log(`Server running at http://localhost:${PORT}`);
	console.log(`Accessible on network at http://${localIP}:${PORT}`);
});
@ @ B*cascade08
 B¬B ¬BÍB*cascade08
ÍBÒB ÒB¤C*cascade08
¤C§C §CÄC*cascade08
ÄCÅC ÅCËC*cascade08
ËCÏC ÏCĞC*cascade08
ĞCÑC ÑCõC*cascade08
õCöC öCùC*cascade08
ùCûC ûC™D*cascade08
™DšD šDµD*cascade08
µD¶D ¶D·D*cascade08
·D¹D ¹DÂD*cascade08
ÂDÃD ÃDÖD*cascade08
ÖD×D ×DÜD*cascade08
ÜDŞD ŞD“E*cascade08
“E”E ”E«E*cascade08
«E­E ­E³E*cascade08
³E½E ½EÂE*cascade08
ÂEÃE ÃEÅE*cascade08
ÅEÆE ÆEİE*cascade08
İEßE ßEôE*cascade08
ôEõE õE÷E*cascade08
÷EøE øEúE*cascade08
úEûE ûE…F*cascade08
…F‡F ‡F F*cascade08
 F¡F ¡F©F*cascade08
©FªF ªF¯F*cascade08
¯F³F ³FµF*cascade08
µF¶F ¶FºF*cascade08
ºF»F »F½F*cascade08
½F¾F ¾FËF*cascade08
ËFüG üG›H*cascade08
›HˆI ˆII*cascade08
I•I •I—I*cascade08
—I’M "(4e6c28288310718ade2f91adc3fea3b5a41725ce28file:///C:/Users/rovie%20segubre/Downloads/new/server.js:.file:///C:/Users/rovie%20segubre/Downloads/new