from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    authenticate_user,
    get_api_user,
    get_current_user_from_session,
    hash_password,
    pop_flash,
    require_api_admin,
    set_flash,
)
from app.database import Base, SessionLocal, engine, get_db
from app.models import FuelItem, FuelType, IssueRecord, User
from app.postgres_lab import (
    add_note,
    create_database_if_not_exists,
    create_demo_table,
    delete_note,
    get_notes,
    get_postgres_info,
    get_recent_fuels,
    mark_note_done,
)
from app.schemas import (
    FuelItemCreate,
    FuelItemRead,
    FuelItemUpdate,
    FuelTypeRead,
    IssueCreate,
    IssueRecordRead,
)


templates = Jinja2Templates(directory="templates")


def seed_database() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        full_name="Адміністратор",
                        hashed_password=hash_password("admin123"),
                        role="admin",
                    ),
                    User(
                        username="operator",
                        full_name="Оператор складу",
                        hashed_password=hash_password("user123"),
                        role="user",
                    ),
                ]
            )

        if db.query(FuelType).count() == 0:
            fuel_types = [
                FuelType(name="Дизель", description="Пальне для вантажного транспорту та тракторів."),
                FuelType(name="Бензин А-95", description="Пальне для легкових автомобілів."),
                FuelType(name="Моторна олива", description="Мастильні матеріали для техніки."),
            ]
            db.add_all(fuel_types)
            db.flush()
            db.add_all(
                [
                    FuelItem(
                        name="Дизель Euro 5",
                        supplier="OKKO",
                        quantity_liters=5200,
                        unit_price=56,
                        description="Основний запас дизельного пального.",
                        fuel_type_id=fuel_types[0].id,
                    ),
                    FuelItem(
                        name="Бензин А-95 резерв",
                        supplier="WOG",
                        quantity_liters=2800,
                        unit_price=59,
                        description="Резерв для службових авто.",
                        fuel_type_id=fuel_types[1].id,
                    ),
                    FuelItem(
                        name="Олива 10W-40",
                        supplier="Shell",
                        quantity_liters=650,
                        unit_price=185,
                        description="Олива для планового обслуговування.",
                        fuel_type_id=fuel_types[2].id,
                    ),
                ]
            )

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database_if_not_exists()
    Base.metadata.create_all(bind=engine)
    create_demo_table()
    seed_database()
    yield


app = FastAPI(title="Облік ПММ", version="2.0.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-in-production")
app.mount("/static", StaticFiles(directory="static"), name="static")


def template_context(request: Request, db: Session, **context):
    payload = {
        "request": request,
        "current_user": get_current_user_from_session(request, db),
        "flash_message": pop_flash(request),
    }
    payload.update(context)
    return payload


def require_html_user(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user_from_session(request, db)
    if user:
        return user
    set_flash(request, "Спочатку увійдіть у систему.")
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


def require_html_admin(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user_from_session(request, db)
    if user and user.role == "admin":
        return user
    set_flash(request, "Доступ лише для адміністратора.")
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request, db: Session = Depends(get_db)):
    fuels = db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).order_by(FuelItem.name.asc()).limit(6).all()
    fuel_types = db.query(FuelType).order_by(FuelType.name.asc()).all()
    return templates.TemplateResponse(
        "index.html",
        template_context(request, db, fuels=fuels, fuel_types=fuel_types),
    )


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", template_context(request, db))


@app.post("/login", include_in_schema=False)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user:
        set_flash(request, "Невірний логін або пароль.")
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    request.session["user_id"] = user.id
    set_flash(request, f"Вхід виконано як {user.full_name}.")
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/fuels", response_class=HTMLResponse, include_in_schema=False)
def fuels_page(request: Request, db: Session = Depends(get_db)):
    fuels = db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).order_by(FuelItem.name.asc()).all()
    return templates.TemplateResponse("books/list.html", template_context(request, db, fuels=fuels))


@app.get("/fuels/{fuel_id}", response_class=HTMLResponse, include_in_schema=False)
def fuel_detail(fuel_id: int, request: Request, db: Session = Depends(get_db)):
    fuel = db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    return templates.TemplateResponse("books/detail.html", template_context(request, db, fuel=fuel))


@app.get("/fuel-types", response_class=HTMLResponse, include_in_schema=False)
def fuel_types_page(request: Request, db: Session = Depends(get_db)):
    fuel_types = db.query(FuelType).options(joinedload(FuelType.fuels)).order_by(FuelType.name.asc()).all()
    return templates.TemplateResponse("categories/list.html", template_context(request, db, fuel_types=fuel_types))


@app.get("/postgres", response_class=HTMLResponse, include_in_schema=False)
def postgres_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "postgres.html",
        template_context(
            request,
            db,
            postgres_info=get_postgres_info(),
            recent_fuels=get_recent_fuels(),
            notes=get_notes(),
        ),
    )


@app.post("/postgres/notes", include_in_schema=False)
def create_postgres_note(request: Request, text: str = Form(...), db: Session = Depends(get_db)):
    user = require_html_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    add_note(text)
    set_flash(request, "Запис додано через Psycopg INSERT.")
    return RedirectResponse("/postgres", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/postgres/notes/{note_id}/done", include_in_schema=False)
def done_postgres_note(note_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_html_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    mark_note_done(note_id)
    set_flash(request, "Запис оновлено через Psycopg UPDATE.")
    return RedirectResponse("/postgres", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/postgres/notes/{note_id}/delete", include_in_schema=False)
def remove_postgres_note(note_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_html_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    delete_note(note_id)
    set_flash(request, "Запис видалено через Psycopg DELETE.")
    return RedirectResponse("/postgres", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/issues", response_class=HTMLResponse, include_in_schema=False)
def issues_page(request: Request, db: Session = Depends(get_db)):
    user = require_html_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    query = db.query(IssueRecord).options(joinedload(IssueRecord.fuel_item)).order_by(IssueRecord.issued_at.desc())
    if user.role != "admin":
        query = query.filter(IssueRecord.user_id == user.id)
    issues = query.all()
    return templates.TemplateResponse(
        "borrowings/list.html",
        template_context(request, db, issues=issues, current_user=user),
    )


@app.post("/fuels/{fuel_id}/issue", include_in_schema=False)
def issue_fuel(
    fuel_id: int,
    request: Request,
    amount_liters: int = Form(...),
    destination: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_html_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    if amount_liters < 1:
        set_flash(request, "Обсяг видачі має бути більшим за нуль.")
        return RedirectResponse(f"/fuels/{fuel_id}", status_code=status.HTTP_303_SEE_OTHER)
    if fuel.quantity_liters < amount_liters:
        set_flash(request, "Недостатній залишок на складі.")
        return RedirectResponse(f"/fuels/{fuel_id}", status_code=status.HTTP_303_SEE_OTHER)

    fuel.quantity_liters -= amount_liters
    db.add(
        IssueRecord(
            user_id=user.id,
            fuel_item_id=fuel.id,
            amount_liters=amount_liters,
            destination=destination,
        )
    )
    db.commit()
    set_flash(request, "Операцію видачі ПММ зафіксовано.")
    return RedirectResponse("/issues", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/fuels/new", response_class=HTMLResponse, include_in_schema=False)
def new_fuel_form(request: Request, db: Session = Depends(get_db)):
    user = require_html_admin(request, db)
    if isinstance(user, RedirectResponse):
        return user
    fuel_types = db.query(FuelType).order_by(FuelType.name.asc()).all()
    return templates.TemplateResponse(
        "books/form.html",
        template_context(
            request,
            db,
            fuel=None,
            fuel_types=fuel_types,
            form_action="/admin/fuels",
            submit_label="Створити позицію ПММ",
            current_user=user,
        ),
    )


@app.post("/admin/fuels", include_in_schema=False)
def create_fuel_html(
    request: Request,
    name: str = Form(...),
    supplier: str = Form(...),
    quantity_liters: int = Form(...),
    unit_price: int = Form(...),
    description: str = Form(""),
    fuel_type_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = require_html_admin(request, db)
    if isinstance(user, RedirectResponse):
        return user
    db.add(
        FuelItem(
            name=name,
            supplier=supplier,
            quantity_liters=quantity_liters,
            unit_price=unit_price,
            description=description,
            fuel_type_id=fuel_type_id,
        )
    )
    db.commit()
    set_flash(request, "Позицію ПММ створено.")
    return RedirectResponse("/fuels", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/fuels/{fuel_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_fuel_form(fuel_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_html_admin(request, db)
    if isinstance(user, RedirectResponse):
        return user
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    fuel_types = db.query(FuelType).order_by(FuelType.name.asc()).all()
    return templates.TemplateResponse(
        "books/form.html",
        template_context(
            request,
            db,
            fuel=fuel,
            fuel_types=fuel_types,
            form_action=f"/admin/fuels/{fuel_id}/edit",
            submit_label="Оновити позицію ПММ",
            current_user=user,
        ),
    )


@app.post("/admin/fuels/{fuel_id}/edit", include_in_schema=False)
def update_fuel_html(
    fuel_id: int,
    request: Request,
    name: str = Form(...),
    supplier: str = Form(...),
    quantity_liters: int = Form(...),
    unit_price: int = Form(...),
    description: str = Form(""),
    fuel_type_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = require_html_admin(request, db)
    if isinstance(user, RedirectResponse):
        return user
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    fuel.name = name
    fuel.supplier = supplier
    fuel.quantity_liters = quantity_liters
    fuel.unit_price = unit_price
    fuel.description = description
    fuel.fuel_type_id = fuel_type_id
    db.commit()
    set_flash(request, "Позицію ПММ оновлено.")
    return RedirectResponse(f"/fuels/{fuel_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/fuels/{fuel_id}/delete", include_in_schema=False)
def delete_fuel_html(fuel_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_html_admin(request, db)
    if isinstance(user, RedirectResponse):
        return user
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    db.delete(fuel)
    db.commit()
    set_flash(request, "Позицію ПММ видалено.")
    return RedirectResponse("/fuels", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/fuel-types", response_model=list[FuelTypeRead], tags=["Fuel Types"])
def api_fuel_types(db: Session = Depends(get_db), _: User = Depends(get_api_user)):
    return db.query(FuelType).order_by(FuelType.name.asc()).all()


@app.get("/api/fuels", response_model=list[FuelItemRead], tags=["Fuel Items"])
def api_fuels(db: Session = Depends(get_db), _: User = Depends(get_api_user)):
    return db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).order_by(FuelItem.name.asc()).all()


@app.get("/api/fuels/{fuel_id}", response_model=FuelItemRead, tags=["Fuel Items"])
def api_fuel_detail(fuel_id: int, db: Session = Depends(get_db), _: User = Depends(get_api_user)):
    fuel = db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    return fuel


@app.post(
    "/api/fuels",
    response_model=FuelItemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Fuel Items"],
    summary="Create a fuel item",
)
def api_create_fuel(payload: FuelItemCreate, db: Session = Depends(get_db), _: User = Depends(require_api_admin)):
    fuel = FuelItem(**payload.model_dump())
    db.add(fuel)
    db.commit()
    return db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).filter(FuelItem.id == fuel.id).first()


@app.put("/api/fuels/{fuel_id}", response_model=FuelItemRead, tags=["Fuel Items"], summary="Update fuel item")
def api_update_fuel(
    fuel_id: int,
    payload: FuelItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    for field, value in payload.model_dump().items():
        setattr(fuel, field, value)
    db.commit()
    return db.query(FuelItem).options(joinedload(FuelItem.fuel_type)).filter(FuelItem.id == fuel.id).first()


@app.delete(
    "/api/fuels/{fuel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Fuel Items"],
    summary="Delete fuel item",
)
def api_delete_fuel(fuel_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_admin)):
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    db.delete(fuel)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/issues", response_model=list[IssueRecordRead], tags=["Issues"])
def api_issues(db: Session = Depends(get_db), user: User = Depends(get_api_user)):
    query = db.query(IssueRecord).options(joinedload(IssueRecord.fuel_item).joinedload(FuelItem.fuel_type))
    if user.role != "admin":
        query = query.filter(IssueRecord.user_id == user.id)
    return query.order_by(IssueRecord.issued_at.desc()).all()


@app.post(
    "/api/issues/{fuel_id}",
    response_model=IssueRecordRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Issues"],
    summary="Issue fuel from stock",
)
def api_issue_fuel(
    fuel_id: int,
    payload: IssueCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_api_user),
):
    fuel = db.query(FuelItem).filter(FuelItem.id == fuel_id).first()
    if not fuel:
        raise HTTPException(status_code=404, detail="Позицію ПММ не знайдено")
    if fuel.quantity_liters < payload.amount_liters:
        raise HTTPException(status_code=400, detail="Недостатній залишок на складі")
    fuel.quantity_liters -= payload.amount_liters
    record = IssueRecord(
        user_id=user.id,
        fuel_item_id=fuel.id,
        amount_liters=payload.amount_liters,
        destination=payload.destination,
    )
    db.add(record)
    db.commit()
    return (
        db.query(IssueRecord)
        .options(joinedload(IssueRecord.fuel_item).joinedload(FuelItem.fuel_type))
        .filter(IssueRecord.id == record.id)
        .first()
    )
