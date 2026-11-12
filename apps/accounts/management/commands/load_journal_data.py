import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.students.models import Student
from apps.academics.models import Course, Teacher, TeacherSalaryRate, StudyGroup, GroupSchedule, Enrollment, EnrollmentPriceHistory
from apps.attendance.models import Lesson, AttendanceRecord
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.payroll.models import SalaryRecord, SalaryPayment
from apps.leads.models import Lead
from apps.academics.services import generate_lessons_from_schedules


class Command(BaseCommand):
    help = "Cleans old dummy test records and imports real students, groups, teachers and courses from journal screenshots"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Majburiy qayta yuklash (hatto bazada 50 dan ortiq o'quvchi bo'lsa ham)"
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        if Student.objects.count() >= 50 and not force:
            self.stdout.write(self.style.NOTICE(
                f"Bazadagi real o'quvchilar allaqachon yuklangan ({Student.objects.count()} ta o'quvchi mavjud). Qayta yuklash o'tkazib yuborildi."
            ))
            return

        self.stdout.write("Tozalash va real ma'lumotlarni yuklash boshlanmoqda...")

        with transaction.atomic():
            # 1. Clear existing operational records
            AttendanceRecord.objects.all().delete()
            Lesson.objects.all().delete()
            GroupSchedule.objects.all().delete()
            PaymentAllocation.objects.all().delete()
            Payment.objects.all().delete()
            MonthlyCharge.objects.all().delete()
            EnrollmentPriceHistory.objects.all().delete()
            Enrollment.objects.all().delete()
            StudyGroup.objects.all().delete()
            SalaryPayment.objects.all().delete()
            SalaryRecord.objects.all().delete()
            TeacherSalaryRate.objects.all().delete()
            Teacher.objects.all().delete()
            Course.objects.all().delete()
            Student.objects.all().delete()
            Lead.objects.all().delete()

            self.stdout.write(self.style.WARNING("Eski test ma'lumotlari (o'quvchi, guruh, kurs, o'qituvchi) tozalandi."))

            today = timezone.now().date()
            start_of_month = today.replace(day=1)

            # 2. Create Courses
            courses_data = {
                'matematika': Course.objects.create(
                    name="Matematika",
                    description="Matematika (DTM va Milliy sertifikatga tayyorlov)",
                    default_monthly_price=Decimal('400000.00'),
                    duration_months=6,
                    is_active=True
                ),
                'kids_english': Course.objects.create(
                    name="Kids English",
                    description="Bolalar uchun ingliz tili darslari",
                    default_monthly_price=Decimal('400000.00'),
                    duration_months=6,
                    is_active=True
                ),
                'rus_tili': Course.objects.create(
                    name="Rus tili",
                    description="Rus tili so'zlashuv va grammatika kursi",
                    default_monthly_price=Decimal('400000.00'),
                    duration_months=6,
                    is_active=True
                ),
                'ona_tili': Course.objects.create(
                    name="Ona tili va Adabiyot",
                    description="Ona tili va adabiyot chuqurlashtirilgan kursi",
                    default_monthly_price=Decimal('400000.00'),
                    duration_months=6,
                    is_active=True
                ),
                'tarix': Course.objects.create(
                    name="Tarix",
                    description="O'zbekiston va Jahon tarixi",
                    default_monthly_price=Decimal('400000.00'),
                    duration_months=6,
                    is_active=True
                ),
            }

            # 3. Create Teachers
            teachers_data = {
                'azizjon': Teacher.objects.create(
                    full_name="Qurbonov Azizjon",
                    phone="+998901234001",
                    specialization="Matematika o'qituvchisi",
                    status=Teacher.Status.ACTIVE
                ),
                'aziza': Teacher.objects.create(
                    full_name="Aziza",
                    phone="+998901234002",
                    specialization="Ingliz tili (Kids English) o'qituvchisi",
                    status=Teacher.Status.ACTIVE
                ),
                'xurshid': Teacher.objects.create(
                    full_name="Xurshid",
                    phone="+998901234003",
                    specialization="Rus tili o'qituvchisi",
                    status=Teacher.Status.ACTIVE
                ),
                'bekzod': Teacher.objects.create(
                    full_name="Bekzod usta",
                    phone="+998901234005",
                    specialization="Ona tili va adabiyot o'qituvchisi",
                    status=Teacher.Status.ACTIVE
                ),
                'sharif': Teacher.objects.create(
                    full_name="Sharif usta",
                    phone="+998901234006",
                    specialization="Tarix fani o'qituvchisi",
                    status=Teacher.Status.ACTIVE
                ),
            }

            # Set default salary rates for teachers
            for t in teachers_data.values():
                TeacherSalaryRate.objects.create(
                    teacher=t,
                    monthly_amount=Decimal('4000000.00'),
                    valid_from=start_of_month
                )

            # Helper to create group and its schedules
            def make_group(name, course_key, teacher_key, days_times, capacity=35):
                group = StudyGroup.objects.create(
                    name=name,
                    course=courses_data[course_key],
                    teacher=teachers_data[teacher_key],
                    capacity=capacity,
                    start_date=start_of_month,
                    is_active=True
                )
                for weekday, s_time, e_time, room in days_times:
                    GroupSchedule.objects.create(
                        group=group,
                        weekday=weekday,
                        start_time=s_time,
                        end_time=e_time,
                        room=room,
                        is_active=True
                    )
                return group

            # 4. Create Groups
            # Dush=1, Sesh=2, Chor=3, Pay=4, Juma=5, Shan=6
            group_matematika = make_group(
                "Matematika (Azizjon)",
                'matematika', 'azizjon',
                [
                    (1, datetime.time(8, 0), datetime.time(9, 30), "101-xona"),
                    (3, datetime.time(8, 0), datetime.time(9, 30), "101-xona"),
                    (5, datetime.time(8, 0), datetime.time(9, 30), "101-xona"),
                ]
            )

            group_kids = make_group(
                "Kids English (Yoshlar)",
                'kids_english', 'aziza',
                [
                    (1, datetime.time(14, 0), datetime.time(15, 30), "102-xona"),
                    (3, datetime.time(14, 0), datetime.time(15, 30), "102-xona"),
                    (6, datetime.time(14, 0), datetime.time(15, 30), "102-xona"),
                ]
            )

            group_rus_ertalab = make_group(
                "Rus tili (Ertalabki 08:00)",
                'rus_tili', 'xurshid',
                [
                    (1, datetime.time(8, 0), datetime.time(9, 30), "103-xona"),
                    (3, datetime.time(8, 0), datetime.time(9, 30), "103-xona"),
                    (5, datetime.time(8, 0), datetime.time(9, 30), "103-xona"),
                ]
            )

            group_rus_tushki = make_group(
                "Rus tili (Tushki 14:00)",
                'rus_tili', 'xurshid',
                [
                    (2, datetime.time(14, 0), datetime.time(15, 30), "103-xona"),
                    (4, datetime.time(14, 0), datetime.time(15, 30), "103-xona"),
                    (6, datetime.time(14, 0), datetime.time(15, 30), "103-xona"),
                ]
            )

            group_ona_tili = make_group(
                "Ona tili (Bekzod usta)",
                'ona_tili', 'bekzod',
                [
                    (1, datetime.time(13, 30), datetime.time(15, 0), "104-xona"),
                    (3, datetime.time(13, 30), datetime.time(15, 0), "104-xona"),
                    (5, datetime.time(13, 30), datetime.time(15, 0), "104-xona"),
                ]
            )

            group_tarix_1 = make_group(
                "Tarix 1 (Dush-Chor-Juma 13:30)",
                'tarix', 'sharif',
                [
                    (1, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                    (3, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                    (5, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                ]
            )

            group_tarix_2 = make_group(
                "Tarix 2 (Sesh-Pay-Shan 13:30)",
                'tarix', 'sharif',
                [
                    (2, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                    (4, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                    (6, datetime.time(13, 30), datetime.time(15, 0), "105-xona"),
                ]
            )

            group_tarix_3 = make_group(
                "Tarix 3 (Qo'shimcha guruh)",
                'tarix', 'sharif',
                [
                    (2, datetime.time(15, 30), datetime.time(17, 0), "105-xona"),
                    (4, datetime.time(15, 30), datetime.time(17, 0), "105-xona"),
                    (6, datetime.time(15, 30), datetime.time(17, 0), "105-xona"),
                ]
            )

            # Helper to enroll students
            student_cache = {}

            def enroll_student(full_name, raw_phone, group, custom_price=None, reason=""):
                clean_phone = raw_phone.strip()
                if not clean_phone.startswith('+'):
                    clean_phone = '+998' + clean_phone.replace(' ', '').replace('-', '')
                
                # Check student cache or create
                cache_key = (full_name.lower().strip(), clean_phone)
                if cache_key in student_cache:
                    student = student_cache[cache_key]
                else:
                    student = Student.objects.create(
                        full_name=full_name.strip(),
                        phone=clean_phone,
                        status=Student.Status.ACTIVE
                    )
                    student_cache[cache_key] = student

                price = Decimal(str(custom_price)) if custom_price else group.course.default_monthly_price
                enr = Enrollment.objects.create(
                    student=student,
                    group=group,
                    start_date=start_of_month,
                    monthly_price=price,
                    custom_price_reason=reason if custom_price and custom_price != group.course.default_monthly_price else "",
                    status=Enrollment.Status.ACTIVE,
                    payment_status=Enrollment.PaymentStatus.PAID if custom_price else Enrollment.PaymentStatus.UNPAID
                )
                if custom_price and custom_price != group.course.default_monthly_price:
                    EnrollmentPriceHistory.objects.create(
                        enrollment=enr,
                        old_price=group.course.default_monthly_price,
                        new_price=price,
                        reason=reason or "Jurnaldan import qilingan chegirma",
                        changed_by=None
                    )
                return enr

            # 5. Populate Students from Journal 1 (Matematika)
            matematika_students = [
                ("Yo'ldoshev X.", "94 479 27 94", 400000, ""),
                ("Mo'minov D.", "93 142 75 44", 400000, ""),
                ("Xakimov A.", "93 329 17 70", 400000, ""),
                ("Quychiyev A.", "77 967 63 51", 400000, ""),
                ("Berdiyev O.", "91 550 59 50", 400000, ""),
                ("Shoumarodov", "95 060 80 11", 400000, ""),
                ("Eshqobilov A.", "77 347 16 07", 400000, ""),
                ("Narxullayeva", "90 471 94 99", 400000, ""),
                ("Toxirova M.", "90 602 12 64", 400000, ""),
                ("Bobomurodova", "91 526 50 25", 400000, ""),
                ("Muxiddinov A.", "93 589 24 81", 400000, ""),
                ("Abdusattorov", "99 076 30 08", 400000, ""),
                ("Abduxalilov A.", "90 100 45 67", 400000, ""),
                ("Komilov D.", "91 936 31 92", 400000, ""),
                ("Hamroboyev T.", "50 102 49 81", 400000, ""),
                ("Ergashev A.", "90 283 59 27", 400000, ""),
                ("Sayfiyev D.", "94 601 27 63", 400000, ""),
                ("Muxiddinov E.", "33 829 33 79", 400000, ""),
                ("Xudoyberdiyev A.", "95 388 95 95", 400000, ""),
                ("Sardorbekov A.", "77 827 87 10", 400000, ""),
            ]
            for name, phone, price, reason in matematika_students:
                enroll_student(name, phone, group_matematika, price, reason)

            # 6. Populate Students from Journal 2 (Kids English)
            kids_students = [
                ("Abdunabiyev", "91 318 48 18", 250000, "Chegirma (1-2-3 tarif)"),
                ("Hodiyayeva", "94 585 12 92", 250000, "Chegirma (1-2-3 tarif)"),
                ("Murtazoyev N.", "90 655 39 44", 250000, "Chegirma (1-2-3 tarif)"),
                ("Rashidov D.", "99 452 88 96", 250000, "Chegirma (250 ming so'm)"),
                ("Baxtiyorovlar", "99 588 45 30", 400000, ""),
                ("Turodullayeva", "94 287 20 28", 400000, ""),
                ("Saydullayeva", "91 335 93 41", 400000, ""),
                ("Tolipova D.", "91 525 20 83", 400000, ""),
                ("Ashurova", "94 491 71 88", 400000, ""),
                ("Xaydarov R.", "90 603 13 85", 400000, ""),
                ("Tursunov A.", "99 982 23 72", 300000, "Chegirma (300 ming so'm)"),
                ("Ravshanov", "50 106 49 97", 400000, ""),
                ("Sanatullayeva", "99 688 73 55", 400000, ""),
                ("Hikmatov M.", "97 393 51 96", 400000, ""),
                ("Axmatov M.", "77 067 10 17", 400000, ""),
                ("To'xtayeva M.", "95 111 26 83", 400000, ""),
                ("To'xtayeva Sh.", "90 600 13 94", 400000, ""),
                ("Shodiyeva Z.", "98 659 29 17", 400000, ""),
                ("Baxriddinova M.", "95 008 06 90", 400000, ""),
                ("Qurbonov", "94 003 87 55", 400000, ""),
                ("Xudoyorova", "90 123 40 21", 400000, ""),
                ("Sayfiyev A.", "90 123 40 22", 400000, ""),
            ]
            for name, phone, price, reason in kids_students:
                enroll_student(name, phone, group_kids, price, reason)

            # 7. Populate Students from Journal 3 (Rus tili Ertalabki)
            rus_ertalab_students = [
                ("Samatov B.", "90 126 65 25", 400000, ""),
                ("Sayimnazarova G.", "94 609 09 95", 400000, ""),
                ("Ernazarova Sh.", "99 742 91 47", 400000, ""),
                ("Ne'matova M.", "77 522 16 96", 400000, ""),
                ("Raxmonberdiyeva", "90 488 90 18", 400000, ""),
                ("Abdug'aniyeva", "91 219 07 27", 400000, ""),
                ("Azimboyeva O.", "50 252 54 09", 400000, ""),
                ("To'liboyeva D.", "90 453 45 90", 300000, "Chegirma (300 ming)"),
                ("Yurayeva M.", "77 827 32 70", 400000, ""),
                ("Fayzullayeva D.", "91 919 54 84", 400000, ""),
                ("Toshpo'latov M.", "90 187 05 85", 400000, ""),
                ("Artikboyev", "99 784 77 18", 200000, "Imtiyozli chegirma (200 ming)"),
                ("Toshboyeva K.", "99 041 36 58", 400000, ""),
                ("Salimova I.", "77 640 25 01", 400000, ""),
                ("Fayzullayev U.", "77 052 81 91", 400000, ""),
                ("Baxodirova D.", "95 721 26 09", 400000, ""),
                ("Bozorova M.", "95 825 85 28", 400000, ""),
                ("Ergasheva S.", "94 182 32 14", 400000, ""),
                ("Mirzayeva S.", "91 117 43 09", 400000, ""),
                ("Sattorova", "77 665 99 00", 400000, ""),
                ("Rustamova", "90 282 46 19", 400000, ""),
                ("Yoqubov Sh.", "70 136 39 06", 250000, "Chegirma (250 ming)"),
                ("Karimboyeva M.", "95 255 58 35", 400000, ""),
                ("Abdusalomova", "94 325 24 61", 400000, ""),
                ("Shermatova M.", "90 001 81 17", 400000, ""),
                ("Murodova M.", "90 123 40 26", 400000, ""),
            ]
            for name, phone, price, reason in rus_ertalab_students:
                enroll_student(name, phone, group_rus_ertalab, price, reason)

            # 8. Populate Students from Journal 4 & 5 (Rus tili Tushki)
            rus_tushki_students = [
                ("Po'latova Z.", "99 046 57 91", 400000, ""),
                ("Hamidova Z.", "99 446 68 89", 400000, ""),
                ("Malanova M.", "90 463 82 88", 400000, ""),
                ("Tursunmurodov", "91 540 20 72", 400000, ""),
                ("Qulbuxova M.", "95 686 86 71", 400000, ""),
                ("Turg'unboyeva", "95 669 43 00", 400000, ""),
                ("Ulug'boyeva B.", "93 542 62 50", 400000, ""),
                ("Qurbonova S.", "91 533 89 53", 400000, ""),
                ("Mardonova F.", "94 269 04 83", 400000, ""),
                ("Ochilov F.", "77 082 84 77", 230000, "Maxsus chegirma (230 ming)"),
                ("Hamroyev B.", "90 043 89 80", 400000, ""),
                ("Mavlonbekova", "93 325 83 20", 400000, ""),
                ("Umarova D.", "95 274 74 81", 400000, ""),
                ("Toshova S.", "90 147 58 98", 400000, ""),
                ("Ortiqova M.", "50 577 10 36", 400000, ""),
                ("Shamsinodirova", "91 551 15 12", 400000, ""),
                ("Abdusamadova", "99 134 20 12", 400000, ""),
            ]
            for name, phone, price, reason in rus_tushki_students:
                enroll_student(name, phone, group_rus_tushki, price, reason)

            # 9. Populate Students from Journal 6 (Ona tili)
            ona_tili_students = [
                ("Shamsiddinov F.", "50 258 25 07", 400000, ""),
                ("Rahmonberdiyev D.", "95 519 06 69", 400000, ""),
                ("Salimova Sevinch", "93 862 10 22", 400000, ""),
                ("Ashurova R.", "95 911 05 13", 400000, ""),
                ("Alimov X.", "95 258 05 10", 399000, "Maxsus tarif (399 ming)"),
                ("Xudoyorova S.", "90 281 84 66", 400000, ""),
            ]
            for name, phone, price, reason in ona_tili_students:
                enroll_student(name, phone, group_ona_tili, price, reason)

            # 10. Populate Students from Journal 8 (Tarix 1 - Dush-Chor-Juma 13:30)
            tarix_1_students = [
                ("Oqboyeva M.", "95 405 65 92", 400000, ""),
                ("Ismatova F.", "91 264 27 10", 400000, ""),
                ("Abdusamiyev", "95 310 07 59", 400000, ""),
                ("Sadillayeva B.", "91 248 49 19", 400000, ""),
                ("Tuxboyev K.", "95 728 19 23", 400000, ""),
                ("Yaxshiboyeva M.", "50 796 62 21", 400000, ""),
                ("Yuldoshev F.", "95 838 15 28", 400000, ""),
                ("Olimov S.", "93 390 51 95", 400000, ""),
                ("Mavlonova R.", "90 515 54 09", 400000, ""),
                ("Mansurova G.", "87 552 04 84", 400000, ""),
                ("Hamroyeva R.", "50 518 59 09", 400000, ""),
                ("Xoliqova E.", "93 420 00 94", 400000, ""),
                ("Norova S.", "50 452 21 76", 400000, ""),
                ("Yarmurodov M.", "91 945 34 84", 400000, ""),
                ("Komiljonov B.", "95 291 77 10", 400000, ""),
                ("Qodirova Oydina", "99 161 82 77", 400000, ""),
                ("Olimova A.", "77 050 05 83", 400000, ""),
                ("Sayfullayeva E.", "77 103 37 87", 400000, ""),
                ("Normurodov", "93 162 40 09", 400000, ""),
                ("Izzatullayeva", "99 342 91 79", 400000, ""),
                ("Ismatova M.", "90 286 44 28", 400000, ""),
                ("Komiljonova", "77 665 99 00", 400000, ""),
                ("Olimova S.", "90 609 23 61", 400000, ""),
                ("Xudoyberdiyeva", "90 465 53 44", 400000, ""),
                ("Toshpo'latov M.", "94 112 38 10", 400000, ""),
                ("Sadullayev J.", "94 244 53 01", 400000, ""),
                ("Nazarova S.", "90 288 08 28", 400000, ""),
                ("Halimova S.", "95 519 92 05", 400000, ""),
            ]
            for name, phone, price, reason in tarix_1_students:
                enroll_student(name, phone, group_tarix_1, price, reason)

            # 11. Populate Students from Journal 9 (Tarix 2 - Sesh-Pay-Shan 13:30)
            tarix_2_students = [
                ("Matov Anvar", "99 785 13 81", 400000, ""),
                ("Toshboyev", "91 764 80 18", 400000, ""),
                ("Qayumov M.", "94 189 62 60", 400000, ""),
                ("Nomozov H.", "90 048 17 81", 400000, ""),
                ("Rustamov S.", "50 501 37 81", 400000, ""),
                ("Mavlonzoda D.", "99 275 19 52", 400000, ""),
                ("Xoldiyorov B.", "90 602 72 61", 400000, ""),
                ("Sultonov X.", "94 451 12 68", 400000, ""),
                ("Baxtiyorova N.", "95 360 16 09", 300000, "Chegirma (300 ming)"),
                ("Choriyev B. (katta)", "90 466 62 82", 400000, ""),
                ("Choriyev B. (kichik)", "99 781 55 00", 400000, ""),
                ("Ergashev", "90 280 80 94", 350000, "Chegirma (350 ming)"),
                ("Fidonkoro 1", "99 336 58 20", 400000, ""),
                ("Fidonkoro 2", "99 210 34 20", 400000, ""),
                ("Rahmatillayev", "99 228 49 19", 400000, ""),
                ("Jamoliddinova", "77 085 05 88", 400000, ""),
                ("Murotboyev S.", "99 941 68 81", 200000, "Imtiyoz (200 ming)"),
                ("Xatamova M.", "77 052 26 93", 400000, ""),
                ("Xatamova Munisa", "90 205 89 76", 400000, ""),
                ("Sultonova M.", "92 023 20 21", 400000, ""),
                ("Keldiyorova", "95 291 80 18", 400000, ""),
                ("Ostonov K.", "77 044 23 21", 400000, ""),
                ("Rahmonova D.", "95 260 21 05", 400000, ""),
                ("Zoirova Dilfuza", "90 280 84 81", 400000, ""),
                ("Olimova T.", "94 624 81 21", 400000, ""),
                ("Abduxalilova", "95 047 24 93", 400000, ""),
                ("Djabbiyeva M.", "77 082 40 81", 400000, ""),
                ("Djurjanova M.", "77 005 81 01", 400000, ""),
                ("Baxtiyorova M.", "77 025 35 26", 400000, ""),
            ]
            for name, phone, price, reason in tarix_2_students:
                enroll_student(name, phone, group_tarix_2, price, reason)

            # 12. Populate Students from Journal 7 (Tarix 3 - Qo'shimcha)
            tarix_3_students = [
                ("Normurodov X.", "90 003 38 99", 400000, ""),
                ("Ruyiyanno E.", "91 837 02 01", 400000, ""),
                ("Hamroyeva M.", "97 003 18 01", 400000, ""),
                ("Xolov A.", "93 351 52 81", 400000, ""),
                ("Xidirov M.", "71 823 70 01", 400000, ""),
                ("Mavlonov J.", "94 523 71 52", 400000, ""),
                ("Hamroyeva Malika", "90 194 75 10", 400000, ""),
                ("Javharov M.", "90 332 10 03", 400000, ""),
                ("Murodova M.", "99 281 48 93", 400000, ""),
                ("Yusufov O.", "99 152 15 12", 400000, ""),
                ("G'ofurov Ziyo", "88 138 45 47", 400000, ""),
                ("Tuyg'unov A.", "91 701 22 01", 400000, ""),
                ("O'lmasboyev B.", "93 039 27 24", 400000, ""),
                ("Mamatqulov F.", "97 414 42 11", 400000, ""),
                ("Muxtorova I.", "95 821 91 92", 400000, ""),
                ("Ibrohimova A.", "99 043 78 19", 400000, ""),
                ("Saydullayeva D.", "77 217 21 21", 400000, ""),
                ("Orziqulov M.", "90 081 82 22", 400000, ""),
                ("Izzatullayev", "94 856 06 18", 400000, ""),
                ("Xudoyberdiyev", "77 290 09 20", 400000, ""),
                ("Qo'chqorov J.", "94 051 66 01", 400000, ""),
            ]
            for name, phone, price, reason in tarix_3_students:
                enroll_student(name, phone, group_tarix_3, price, reason)

            # 13. Generate lessons for all groups for the current month
            all_groups = StudyGroup.objects.all()
            total_lessons = 0
            for grp in all_groups:
                end_of_month = (start_of_month + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
                created_lessons = generate_lessons_from_schedules(
                    group=grp,
                    start_date=start_of_month,
                    end_date=end_of_month
                )
                total_lessons += len(created_lessons)

            self.stdout.write(self.style.SUCCESS(
                f"Yuklash muvaffaqiyatli yakunlandi!\n"
                f"- Kurslar soni: {Course.objects.count()} ta\n"
                f"- O'qituvchilar soni: {Teacher.objects.count()} ta\n"
                f"- Guruhlar soni: {StudyGroup.objects.count()} ta\n"
                f"- O'quvchilar soni: {Student.objects.count()} ta\n"
                f"- Guruhlarga a'zoliklar (enrollments): {Enrollment.objects.count()} ta\n"
                f"- Dars jadvallari slotlari: {GroupSchedule.objects.count()} ta\n"
                f"- Joriy oy uchun yaratilgan darslar: {total_lessons} ta"
            ))
