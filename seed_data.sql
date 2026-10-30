-- ============================================================================
-- EDUSPHERE SQL DATABASE SEED FILE (Matches app.py 'papers' table 100%)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mock_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam TEXT NOT NULL,
    subject TEXT NOT NULL,
    question TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL,
    explanation TEXT NOT NULL,
    official_source TEXT NOT NULL
);

INSERT INTO papers (exam, year, subject, session, title, description, source_url, file_name, stored_name, file_size, downloads, created_at, updated_at) VALUES
-- ==================== CBSE CLASS 12 (Sample Papers, Solutions & NCERT Books) ====================
('cbse-12', 2025, 'Physics', 'SQP 2024-25', 'CBSE Class 12 Physics Official Sample Question Paper', 'Official CBSE Class 12 Physics Sample Paper for 2025 Board Exam.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-SQP.pdf', 'Physics-SQP-2025.pdf', 'EXTERNAL_URL', 1048576, 342, 1730000000, 1730000000),
('cbse-12', 2025, 'Physics', 'Solution Sheet', 'CBSE Class 12 Physics Official Marking Scheme & Solutions', 'Step-by-step official CBSE solution sheet for Class 12 Physics SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-MS.pdf', 'Physics-MS-2025.pdf', 'EXTERNAL_URL', 1248576, 295, 1730000000, 1730000000),
('cbse-12', 2025, 'Mathematics', 'SQP 2024-25', 'CBSE Class 12 Mathematics Official Sample Question Paper', 'Official CBSE Class 12 Mathematics Sample Paper for 2025 Board Exam.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-SQP.pdf', 'Maths-SQP-2025.pdf', 'EXTERNAL_URL', 1148576, 418, 1730000000, 1730000000),
('cbse-12', 2025, 'Mathematics', 'Solution Sheet', 'CBSE Class 12 Mathematics Official Marking Scheme & Solutions', 'Official CBSE solution sheet and marking scheme for Class 12 Maths.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-MS.pdf', 'Maths-MS-2025.pdf', 'EXTERNAL_URL', 1348576, 360, 1730000000, 1730000000),
('cbse-12', 2025, 'Chemistry', 'SQP 2024-25', 'CBSE Class 12 Chemistry Official Sample Question Paper', 'Official CBSE Class 12 Chemistry Sample Paper.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Chemistry-SQP.pdf', 'Chemistry-SQP-2025.pdf', 'EXTERNAL_URL', 948576, 275, 1730000000, 1730000000),
('cbse-12', 2025, 'Chemistry', 'Solution Sheet', 'CBSE Class 12 Chemistry Official Marking Scheme & Solutions', 'Official CBSE Chemistry solution sheet.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Chemistry-MS.pdf', 'Chemistry-MS-2025.pdf', 'EXTERNAL_URL', 1048576, 210, 1730000000, 1730000000),
('cbse-12', 2025, 'Biology', 'SQP 2024-25', 'CBSE Class 12 Biology Official Sample Question Paper', 'Official CBSE Class 12 Biology Sample Paper.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Biology-SQP.pdf', 'Biology-SQP-2025.pdf', 'EXTERNAL_URL', 1048576, 195, 1730000000, 1730000000),
('cbse-12', 2025, 'Biology', 'Solution Sheet', 'CBSE Class 12 Biology Official Marking Scheme & Solutions', 'Official CBSE Class 12 Biology Solutions.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Biology-MS.pdf', 'Biology-MS-2025.pdf', 'EXTERNAL_URL', 1048576, 165, 1730000000, 1730000000),
('cbse-12', 2025, 'English Core', 'SQP 2024-25', 'CBSE Class 12 English Core Official Sample Paper', 'Official CBSE Class 12 English Core Sample Paper.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/EnglishCore-SQP.pdf', 'EnglishCore-SQP-2025.pdf', 'EXTERNAL_URL', 848576, 390, 1730000000, 1730000000),
('cbse-12', 2025, 'English Core', 'Solution Sheet', 'CBSE Class 12 English Core Official Marking Scheme', 'Official CBSE Class 12 English Core Solution Sheet.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/EnglishCore-MS.pdf', 'EnglishCore-MS-2025.pdf', 'EXTERNAL_URL', 948576, 310, 1730000000, 1730000000),
('cbse-12', 2024, 'Physics', 'NCERT Book', 'NCERT Class 12 Physics Chapter 1: Electric Charges & Fields', 'Official NCERT Class 12 Physics Textbook PDF.', 'https://ncert.nic.in/textbook/pdf/leph101.pdf', 'NCERT-Class12-Physics-Ch1.pdf', 'EXTERNAL_URL', 2548576, 540, 1730000000, 1730000000),
('cbse-12', 2024, 'Mathematics', 'NCERT Book', 'NCERT Class 12 Maths Chapter 1: Relations & Functions', 'Official NCERT Class 12 Mathematics Textbook PDF.', 'https://ncert.nic.in/textbook/pdf/lemh101.pdf', 'NCERT-Class12-Maths-Ch1.pdf', 'EXTERNAL_URL', 2148576, 515, 1730000000, 1730000000),
('cbse-12', 2024, 'Chemistry', 'NCERT Book', 'NCERT Class 12 Chemistry Chapter 1: Solutions', 'Official NCERT Class 12 Chemistry Textbook PDF.', 'https://ncert.nic.in/textbook/pdf/lech101.pdf', 'NCERT-Class12-Chem-Ch1.pdf', 'EXTERNAL_URL', 2248576, 460, 1730000000, 1730000000),

-- ==================== CBSE CLASS 10 (Sample Papers, Solutions & NCERT Books) ====================
('cbse-10', 2025, 'Science', 'SQP 2024-25', 'CBSE Class 10 Science Official Sample Question Paper', 'Official CBSE Class 10 Science SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/Science-SQP.pdf', 'Class10-Science-SQP.pdf', 'EXTERNAL_URL', 1148576, 450, 1730000000, 1730000000),
('cbse-10', 2025, 'Science', 'Solution Sheet', 'CBSE Class 10 Science Official Marking Scheme & Solutions', 'Official CBSE Class 10 Science Solutions.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/Science-MS.pdf', 'Class10-Science-MS.pdf', 'EXTERNAL_URL', 1248576, 385, 1730000000, 1730000000),
('cbse-10', 2025, 'Mathematics', 'SQP 2024-25', 'CBSE Class 10 Mathematics Standard Sample Paper', 'Official CBSE Class 10 Maths Standard SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/MathsStandard-SQP.pdf', 'Class10-Maths-SQP.pdf', 'EXTERNAL_URL', 1048576, 495, 1730000000, 1730000000),
('cbse-10', 2025, 'Mathematics', 'Solution Sheet', 'CBSE Class 10 Mathematics Standard Solution Sheet', 'Official CBSE Class 10 Maths Standard Marking Scheme.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/MathsStandard-MS.pdf', 'Class10-Maths-MS.pdf', 'EXTERNAL_URL', 1148576, 410, 1730000000, 1730000000),
('cbse-10', 2025, 'Social Science', 'SQP 2024-25', 'CBSE Class 10 Social Science Official Sample Paper', 'Official CBSE Class 10 Social Science SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/SocialScience-SQP.pdf', 'Class10-SST-SQP.pdf', 'EXTERNAL_URL', 1348576, 290, 1730000000, 1730000000),
('cbse-10', 2025, 'English', 'SQP 2024-25', 'CBSE Class 10 English Language & Literature Sample Paper', 'Official CBSE Class 10 English SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/EnglishL-SQP.pdf', 'Class10-English-SQP.pdf', 'EXTERNAL_URL', 948576, 320, 1730000000, 1730000000),
('cbse-10', 2024, 'Science', 'NCERT Book', 'NCERT Class 10 Science Chapter 1: Chemical Reactions', 'Official NCERT Class 10 Science Textbook PDF.', 'https://ncert.nic.in/textbook/pdf/jesc101.pdf', 'NCERT-Class10-Science-Ch1.pdf', 'EXTERNAL_URL', 2048576, 610, 1730000000, 1730000000),

-- ==================== IIT JEE ADVANCED & NTA JEE MAIN ====================
('jee-advanced', 2024, 'Physics, Chemistry & Mathematics', 'Paper 1', 'JEE Advanced 2024 Official Question Paper 1', 'Official IIT JEE Advanced 2024 Paper 1 PDF.', 'https://jeeadv.ac.in/past_qps/2024_1_English.pdf', 'JEE-Adv-2024-Paper1.pdf', 'EXTERNAL_URL', 3148576, 620, 1730000000, 1730000000),
('jee-advanced', 2024, 'Physics, Chemistry & Mathematics', 'Paper 2', 'JEE Advanced 2024 Official Question Paper 2', 'Official IIT JEE Advanced 2024 Paper 2 PDF.', 'https://jeeadv.ac.in/past_qps/2024_2_English.pdf', 'JEE-Adv-2024-Paper2.pdf', 'EXTERNAL_URL', 3148576, 580, 1730000000, 1730000000),
('jee-advanced', 2023, 'Physics, Chemistry & Mathematics', 'Paper 1', 'JEE Advanced 2023 Official Question Paper 1', 'Official IIT JEE Advanced 2023 Paper 1 PDF.', 'https://jeeadv.ac.in/past_qps/2023_1_English.pdf', 'JEE-Adv-2023-Paper1.pdf', 'EXTERNAL_URL', 2948576, 490, 1730000000, 1730000000),
('jee-advanced', 2022, 'Physics, Chemistry & Mathematics', 'Paper 1', 'JEE Advanced 2022 Official Question Paper 1', 'Official IIT JEE Advanced 2022 Paper 1 PDF.', 'https://jeeadv.ac.in/past_qps/2022_1_English.pdf', 'JEE-Adv-2022-Paper1.pdf', 'EXTERNAL_URL', 2848576, 430, 1730000000, 1730000000),
('jee-main', 2025, 'Physics, Chemistry & Mathematics', 'Session 1', 'NTA JEE Main Official Sample Question Paper & Solutions', 'Official NTA JEE Main Practice Paper.', 'https://jeemain.nta.nic.in/', 'JEE-Main-2025-Sample.pdf', 'EXTERNAL_URL', 2548576, 780, 1730000000, 1730000000),

-- ==================== NTA NEET UG ====================
('neet', 2024, 'Physics, Chemistry & Biology', 'Main Exam', 'NTA NEET UG 2024 Official Question Paper & Answer Key', 'Official NTA NEET UG Paper.', 'https://neet.nta.nic.in/', 'NEET-UG-2024.pdf', 'EXTERNAL_URL', 3548576, 890, 1730000000, 1730000000),

-- ==================== CISCE: ISC CLASS 12 & ICSE CLASS 10 ====================
('isc-12', 2025, 'Physics', 'Specimen Paper', 'ISC Class 12 Physics Official Specimen Paper 2025', 'Official CISCE ISC Class 12 Physics Specimen Paper.', 'https://cisce.org/specimen-question-papers-isc-class-xii-2025/', 'ISC-12-Physics-2025.pdf', 'EXTERNAL_URL', 1048576, 185, 1730000000, 1730000000),
('isc-12', 2025, 'Mathematics', 'Specimen Paper', 'ISC Class 12 Mathematics Official Specimen Paper 2025', 'Official CISCE ISC Class 12 Maths Specimen Paper.', 'https://cisce.org/specimen-question-papers-isc-class-xii-2025/', 'ISC-12-Maths-2025.pdf', 'EXTERNAL_URL', 1148576, 205, 1730000000, 1730000000),
('icse-10', 2025, 'Physics', 'Specimen Paper', 'ICSE Class 10 Physics Official Specimen Paper 2025', 'Official CISCE ICSE Class 10 Physics Specimen Paper.', 'https://cisce.org/specimen-question-papers-icse-class-x-2025/', 'ICSE-10-Physics-2025.pdf', 'EXTERNAL_URL', 948576, 230, 1730000000, 1730000000),
('icse-10', 2025, 'Mathematics', 'Specimen Paper', 'ICSE Class 10 Mathematics Official Specimen Paper 2025', 'Official CISCE ICSE Class 10 Maths Specimen Paper.', 'https://cisce.org/specimen-question-papers-icse-class-x-2025/', 'ICSE-10-Maths-2025.pdf', 'EXTERNAL_URL', 1048576, 260, 1730000000, 1730000000);

-- ==================== OFFICIAL MOCK TEST QUESTIONS ====================
INSERT INTO mock_tests (exam, subject, question, option_a, option_b, option_c, option_d, correct_option, explanation, official_source) VALUES
('jee-main', 'Physics', 'Two point charges +8q and -2q are located at x = 0 and x = L respectively. The point on the x-axis at which the net electric field is zero is:', '8L', '4L', '2L', 'L/4', 'C', 'By Coulomb Law, k(8q)/x^2 = k(2q)/(x-L)^2 => 2/x = 1/(x-L) => x = 2L.', 'NTA JEE Main Official'),
('cbse-12', 'Mathematics', 'If A is a square matrix of order 3 such that |adj A| = 64, then the value of |A| is:', '8 only', '-8 only', '64', '8 or -8', 'D', '|adj A| = |A|^(n-1). For n=3, |A|^2 = 64 => |A| = +8 or -8.', 'CBSE Class 12 SQP');
